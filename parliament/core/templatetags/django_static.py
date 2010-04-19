# python
import os
import re
import sys
import stat
from glob import glob
from collections import defaultdict
from cStringIO import StringIO
from subprocess import Popen, PIPE

try:
    from slimmer import css_slimmer, guessSyntax, html_slimmer, js_slimmer, xhtml_slimmer
    slimmer = 'installed'
except ImportError:
    slimmer = None
    import warnings
    warnings.warn("slimmer is not installed. (easy_install slimmer)")

if sys.platform == "win32":
    _CAN_SYMLINK = False
else:
    _CAN_SYMLINK = True

# django 
from django import template
from django.conf import settings

register = template.Library()

## These two methods are put here if someone wants to access the django_static
## functionality from code rather than from a django template
## E.g.
##   from django_static import slimfile
##   print slimfile('/css/foo.js')

def slimfile(filename):
    return _static_file(filename,
                        symlink_if_possible=_CAN_SYMLINK,
                        optimize_if_possible=True)

def staticfile(filename):
    return _static_file(filename,
                        symlink_if_possible=_CAN_SYMLINK,
                        optimize_if_possible=False)


class SlimContentNode(template.Node):
    
    def __init__(self, nodelist, format=None):
        self.nodelist = nodelist
        self.format = format
        
    def render(self, context):
        code = self.nodelist.render(context)
        if slimmer is None:
            return code
        
        if self.format not in ('css','js','html','xhtml'):
            self.format = guessSyntax(code)
            
        if self.format == 'css':
            return css_slimmer(code)
        elif self.format in ('js', 'javascript'):
            return js_slimmer(code)
        elif self.format == 'xhtml':
            return xhtml_slimmer(code)
        elif self.format == 'html':
            return html_slimmer(code)
            
        return code

    

@register.tag(name='slimcontent')
def do_slimcontent(parser, token):
    nodelist = parser.parse(('endslimcontent',))
    parser.delete_first_token()
    
    _split = token.split_contents()
    format = ''
    if len(_split) > 1:
        tag_name, format = _split
        if not (format[0] == format[-1] and format[0] in ('"', "'")):
            raise template.TemplateSyntaxError, \
                          "%r tag's argument should be in quotes" % tag_name
                          
    return SlimContentNode(nodelist, format[1:-1])



@register.tag(name='slimfile')
def slimfile_node(parser, token):
    """For example:
         {% slimfile "/js/foo.js" %}
         or
         {% slimfile "/js/foo.js" as variable_name %}
    Or for multiples:
         {% slimfile "/foo.js; /bar.js" %}
         or 
         {% slimfile "/foo.js; /bar.js" as variable_name %}
    """
    return staticfile_node(parser, token, optimize_if_possible=True)


@register.tag(name='staticfile')
def staticfile_node(parser, token, optimize_if_possible=False):
    """For example:
         {% staticfile "/js/foo.js" %}
         or
         {% staticfile "/js/foo.js" as variable_name %}
    Or for multiples:
         {% staticfile "/foo.js; /bar.js" %}
         or 
         {% staticfile "/foo.js; /bar.js" as variable_name %}
    """
    args = token.split_contents()
    tag = args[0]
    
    if len(args) == 4 and args[-2] == 'as':
        context_name = args[-1]
        args = args[:-2]
    else:
        context_name = None
    
    filename = parser.compile_filter(args[1])
    
    return StaticFileNode(filename,
                          symlink_if_possible=_CAN_SYMLINK,
                          optimize_if_possible=optimize_if_possible)
    

class StaticFileNode(template.Node):
    
    def __init__(self, filename_var,
                 optimize_if_possible=False, 
                 symlink_if_possible=False,
                 context_name=None):
        self.filename_var = filename_var
        self.optimize_if_possible = optimize_if_possible
        self.symlink_if_possible = symlink_if_possible
        self.context_name = context_name
        
    def render(self, context):
        filename = self.filename_var.resolve(context)
        if not getattr(settings, 'DJANGO_STATIC', False):
            return filename
        
        new_filename = _static_file([x.strip() for x in filename.split(';')],
                            optimize_if_possible=self.optimize_if_possible,
                            symlink_if_possible=self.symlink_if_possible)
        if self.context_name:
            context[self.context_name] = new_filename
            return ''
        return new_filename
    

@register.tag(name='slimall')
def do_slimallfiles(parser, token):
    nodelist = parser.parse(('endslimall',))
    parser.delete_first_token()
    
    return StaticFilesNode(nodelist,
                           symlink_if_possible=_CAN_SYMLINK,
                           optimize_if_possible=True)


@register.tag(name='staticall')
def do_staticallfiles(parser, token):
    nodelist = parser.parse(('endstaticall',))
    parser.delete_first_token()
    
    return StaticFilesNode(nodelist,
                           symlink_if_possible=_CAN_SYMLINK,
                           optimize_if_possible=False)




scripts_regex = re.compile('<script [^>]*src=["\']([^"\']+)["\'].*?</script>')
styles_regex = re.compile('<link.*?href=["\']([^"\']+)["\'].*?>', re.M|re.DOTALL)
img_regex = re.compile('<img.*?src=["\']([^"\']+)["\'].*?>', re.M|re.DOTALL)


class StaticFilesNode(template.Node):
    """find all static files in the wrapped code and run staticfile (or 
    slimfile) on them all by analyzing the code.
    """
    def __init__(self, nodelist, optimize_if_possible=False,
                 symlink_if_possible=False):
        self.nodelist = nodelist
        self.optimize_if_possible = optimize_if_possible
        
        self.symlink_if_possible = symlink_if_possible
        
    def render(self, context):
        """inspect the code and look for files that can be turned into combos.
        Basically, the developer could type this:
        {% slimall %}
          <link href="/one.css"/>
          <link href="/two.css"/>
        {% endslimall %}
        And it should be reconsidered like this:
          <link href="{% slimfile "/one.css;/two.css" %}"/>
        which we already have routines for doing.
        """
        code = self.nodelist.render(context)
        if not getattr(settings, 'DJANGO_STATIC', False):
            return code
        
        new_js_filenames = []
        for match in scripts_regex.finditer(code):
            whole_tag = match.group()
            for filename in match.groups():
                
                optimize_if_possible = self.optimize_if_possible
                if optimize_if_possible and \
                  (filename.endswith('.min.js') or filename.endswith('.minified.js')):
                    # Override! Because we simply don't want to run slimmer
                    # on files that have the file extension .min.js
                    optimize_if_possible = False
                
                new_js_filenames.append(filename)
                code = code.replace(whole_tag, '')
                
        # Now, we need to combine these files into one
        if new_js_filenames:
            new_js_filename = _static_file(new_js_filenames,
                               optimize_if_possible=optimize_if_possible,
                               symlink_if_possible=self.symlink_if_possible)
        else:
            new_js_filename = None
            
        new_image_filenames = []
        def image_replacer(match):
            tag = match.group()
            for filename in match.groups():
                new_filename = _static_file(filename,
                                            symlink_if_possible=self.symlink_if_possible)
                if new_filename != filename: 
                    tag = tag.replace(filename, new_filename)
            return tag
        code = img_regex.sub(image_replacer, code)
        
        new_css_filenames = defaultdict(list)
        
        # It's less trivial with CSS because we can't combine those that are
        # of different media
        media_regex = re.compile('media=["\']([^"\']+)["\']')
        for match in styles_regex.finditer(code):
            whole_tag = match.group()
            try:
                media_type = media_regex.findall(whole_tag)[0]
            except IndexError:
                # Because it's so common
                media_type = 'screen'
                
            for filename in match.groups():
                new_css_filenames[media_type].append(filename)
                code = code.replace(whole_tag, '')
                
        # Now, we need to combine these files into one
        new_css_filenames_combined = {}
        if new_css_filenames:
            for media_type, filenames in new_css_filenames.items():
                new_css_filenames_combined[media_type] = \
                  _static_file(filenames,
                               optimize_if_possible=self.optimize_if_possible,
                               symlink_if_possible=self.symlink_if_possible)
                
        # When we make up this new file we have to understand where to write it
        try:
            DJANGO_STATIC_SAVE_PREFIX = settings.DJANGO_STATIC_SAVE_PREFIX
        except AttributeError:
            DJANGO_STATIC_SAVE_PREFIX = ''
        PREFIX = DJANGO_STATIC_SAVE_PREFIX and DJANGO_STATIC_SAVE_PREFIX or \
          settings.MEDIA_ROOT
        
        # If there was a file with the same name there already but with a different
        # timestamp, then delete it
            
        MEDIA_URL = getattr(settings, 'DJANGO_STATIC_MEDIA_URL', None)
        DJANGO_STATIC_NAME_PREFIX = getattr(settings, 'DJANGO_STATIC_NAME_PREFIX', '')
            
        if new_js_filename:
            # Now is the time to apply the name prefix if there is one
            new_tag = '<script type="text/javascript" src="%s"></script>' % \
              new_js_filename
            code = "%s%s" % (new_tag, code)
        
        for media_type, new_css_filename in new_css_filenames_combined.items():
            new_tag = '<link rel="stylesheet" type="text/css" media="%s" href="%s"/>' % \
              (media_type, new_css_filename)
            code = "%s%s" % (new_tag, code)
        
        return code
    
_FILE_MAP = {}

referred_css_images_regex = re.compile('url\(([^\)]+)\)')

def _static_file(filename,
                 optimize_if_possible=False,
                 symlink_if_possible=False,
                 warn_no_file=True):
    """
    """
    if not getattr(settings, 'DJANGO_STATIC', False):
        return filename
    
    DJANGO_STATIC_SAVE_PREFIX = getattr(settings, 'DJANGO_STATIC_SAVE_PREFIX', '')
    DJANGO_STATIC_NAME_PREFIX = getattr(settings, 'DJANGO_STATIC_NAME_PREFIX', '')

    DEBUG = settings.DEBUG
    PREFIX = DJANGO_STATIC_SAVE_PREFIX and DJANGO_STATIC_SAVE_PREFIX or \
      settings.MEDIA_ROOT
    
    try:
        MEDIA_URL = settings.DJANGO_STATIC_MEDIA_URL
    except AttributeError:
        MEDIA_URL = None
        
    def wrap_up(filename):
        if MEDIA_URL:
            return MEDIA_URL + filename
        return filename
    
    is_combined_files = isinstance(filename, list)
    if is_combined_files and len(filename) == 1:
        # e.g. passed a list of files but only one so treat it like a 
        # single file
        filename = filename[0]
        is_combined_files = False
    
    if is_combined_files:
        map_key = ';'.join(filename)
    else:
        map_key = filename
        
    new_filename, m_time = _FILE_MAP.get(map_key, (None, None))
    
    # we might already have done a conversion but the question is
    # if the javascript or css file has changed. This we only want
    # to bother with when in DEBUG mode because it adds one more 
    # unnecessary operation.
    if new_filename:
        if DEBUG:
            # need to check if the original has changed
            old_new_filename = new_filename
            new_filename = None
        else:
            # This is really fast and only happens when NOT in DEBUG mode
            # since it doesn't do any comparison 
            return wrap_up(new_filename)
    else:
        # This is important so that we can know that there wasn't an 
        # old file which will help us know we don't need to delete 
        # the old one
        old_new_filename = None
        
        
    if not new_filename:
        if is_combined_files:
            # It's a list! We have to combine it into one file
            new_file_content = StringIO()
            each_m_times = []
            extension = None
            filenames = []
            for each in filename:
                filepath = _filename2filepath(each, settings.MEDIA_ROOT)
                if not os.path.isfile(filepath):
                    raise OSError(filepath)
                
                if extension:
                    if os.path.splitext(filepath)[1] != extension:
                        raise ValueError("Mismatching file extension in combo %r" % \
                          each)
                else:
                    extension = os.path.splitext(filepath)[1]
                each_m_times.append(os.stat(filepath)[stat.ST_MTIME])
                new_file_content.write(open(filepath, 'r').read().strip())
                new_file_content.write('\n')
            
            filename = _combine_filenames(filename)
            new_m_time = max(each_m_times)
            
        else:
            filepath = _filename2filepath(filename, settings.MEDIA_ROOT)
            if not os.path.isfile(filepath):
                if warn_no_file:
                    import warnings; warnings.warn("Can't find file %s" % filepath)
                return wrap_up(filename)
            
            new_m_time = os.stat(filepath)[stat.ST_MTIME]
            
        if m_time:
            # we had the filename in the map
            if m_time != new_m_time:
                # ...but it has changed!
                m_time = None
            else:
                # ...and it hasn't changed!
                return wrap_up(old_new_filename)
            
        if not m_time:
            # We did not have the filename in the map OR it has changed
            apart = os.path.splitext(filename)
            new_filename = ''.join([apart[0], 
                                '.%s' % new_m_time,
                                apart[1]])
            
            fileinfo = (DJANGO_STATIC_NAME_PREFIX + new_filename, new_m_time)
                
            _FILE_MAP[map_key] = fileinfo
            if old_new_filename:
                old_new_filename = old_new_filename.replace(DJANGO_STATIC_NAME_PREFIX, '')
                old_new_filepath = _filename2filepath(old_new_filename, PREFIX)
                os.remove(old_new_filepath)

    new_filepath = _filename2filepath(new_filename, PREFIX)
     
    # Files are either slimmered or symlinked or just copied. Basically, only
    # .css and .js can be slimmered but not all are. For example, an already
    # minified say jquery.min.js doesn't need to be slimmered nor does it need
    # to be copied. 
    # If you're on windows, it will always have to do a copy. 
    # When symlinking, what the achievement is is that it gives the file a 
    # unique and different name than the original. 
    #
    # The caller of this method is responsible for dictacting if we're should
    # slimmer and if we can symlink.
    
    if optimize_if_possible:
        # Then we expect to be able to modify the content and we will 
        # definitely need to write a new file.
        if is_combined_files:
            content = new_file_content.getvalue()
        else:
            content = open(filepath).read()
        if new_filename.endswith('.js') and has_optimizer(JS):
            content = optimize(content, JS)
        elif new_filename.endswith('.css') and has_optimizer(CSS):
            content = optimize(content, CSS)
            # and _static_file() all images refered in the CSS file itself
            path_for_relative = os.path.dirname(filename)
            def replacer(match):
                #css_filename = filename
                filename = match.groups()[0]
                if (filename.startswith('"') and filename.endswith('"')) or \
                  (filename.startswith("'") and filename.endswith("'")):
                    filename = filename[1:-1]
                orig_filename = filename
                
                if filename[0] != '/':
                    filename = os.path.join(path_for_relative, filename)
                # It's really quite common that the CSS file refers to the file 
                # that doesn't exist because if you refer to an image in CSS for
                # a selector you never use you simply don't suffer.
                # That's why we say not to warn on nonexisting files
                new_filename = _static_file(filename, symlink_if_possible=symlink_if_possible,
                                            warn_no_file=DEBUG and True or False)
                return match.group().replace(orig_filename, new_filename)
            
            content = referred_css_images_regex.sub(replacer, content)
        elif slimmer:
            raise ValueError(
              "Unable to slimmer file %s. Unrecognized extension" % new_filename)
        #print "** STORING:", new_filepath
        open(new_filepath, 'w').write(content)
    elif symlink_if_possible and not is_combined_files:
        #print "** SYMLINK:", filepath, '-->', new_filepath
        
        # The reason we have to do this strange while loop is that it can 
        # happen that in between the time it takes to destroy symlink till you 
        # can create it, another thread or process might be trying to do the
        # exact same thing with just a fraction of a second difference, thus
        # making it possible to, at the time of creating the symlink, that it's
        # already there which will raise an OSError.
        #
        # This is quite possible when Django for example starts multiple fcgi 
        # threads roughly all at the same time. An alternative approach would
        # be to store the global variable _FILE_MAP in a cache or something 
        # which would effectively make it thread safe but that has the annoying
        # disadvantage that it remains in the cache between server restarts and
        # for a production environment, server restarts very often happen 
        # because you have upgraded the code (and the static files). So, an
        # alternative is to use a cache so that thread number 2, number 3 etc
        # gets the file mappings of the first thread and then let this cache
        # only last for a brief amount of time. That amount of time would 
        # basically be equivalent of the time the sys admin or developer would
        # have to wait between new code deployment and refreshed symlinks for
        # the static files. That feels convoluted and complex so I've decided
        # to instead use this rather obtuse while loop which is basically built
        # to try X number of times. If it still fails after X number of attempts
        # there's something else wrong with the IO which needs to bubble up.
        _max_attempts = 10
        while True:
            try:
                if os.path.lexists(new_filepath):
                    # since in the other cases we write a new file, it doesn't matter
                    # that the file existed before.
                    # That's not the case with symlinks
                    os.unlink(new_filepath)
        
                os.symlink(filepath, new_filepath)
                break
            except OSError:
                _max_attempts -= 1
                if _max_attempts <= 0:
                    raise
    else:
        #print "** STORING COMBO:", new_filepath
        open(new_filepath, 'w').write(new_file_content.getvalue())
        
    return wrap_up(DJANGO_STATIC_NAME_PREFIX + new_filename)


def _mkdir(newdir):
    """works the way a good mkdir should :)
        - already exists, silently complete
        - regular file in the way, raise an exception
        - parent directory(ies) does not exist, make them as well
    """
    if os.path.isdir(newdir):
        pass
    elif os.path.isfile(newdir):
        raise OSError("a file with the same name as the desired " \
                      "dir, '%s', already exists." % newdir)
    else:
        head, tail = os.path.split(newdir)
        if head and not os.path.isdir(head):
            _mkdir(head)
        if tail:
            os.mkdir(newdir)
            
            
def _filename2filepath(filename, media_root):
    # The reason we're doing this is because the templates will 
    # look something like this:
    # src="{{ MEDIA_URL }}/css/foo.css"
    # and if (and often happens in dev mode) MEDIA_URL will 
    # just be ''
    
    if filename.startswith('/'):
        path = os.path.join(media_root, filename[1:])
    else:
        path = os.path.join(media_root, filename)
        
    if not os.path.isdir(os.path.dirname(path)):
        _mkdir(os.path.dirname(path))
        
    return path
    
    
    
def _combine_filenames(filenames):
    """Return a new filename to use as the combined file name for a 
    bunch files. 
    A precondition is that they all have the same file extension
    
    Given that the list of files can have different paths, we aim to use the 
    most common path.
    
    Example:
      /somewhere/else/foo.js
      /somewhere/bar.js
      /somewhere/different/too/foobar.js
    The result will be
      /somewhere/foo_bar_foobar.js
      
    Another thing to note, if the filenames have timestamps in them, combine
    them all and use the highest timestamp.
    
    """
    path = None
    names = []
    extension = None
    timestamps = []
    for filename in filenames:
        name = os.path.basename(filename)
        if not extension:
            extension = os.path.splitext(name)[1]
        elif os.path.splitext(name)[1] != extension:
            raise ValueError("Can't combine multiple file extensions")
        
        for each in re.finditer('\.\d{10}\.', name):
            timestamps.append(int(each.group().replace('.','')))
            name = name.replace(each.group(), '.')
        name = os.path.splitext(name)[0]
        names.append(name)
        
        if path is None:
            path = os.path.dirname(filename)
        else:
            if len(os.path.dirname(filename)) < len(path):
                path = os.path.dirname(filename)
    
    
    new_filename = '_'.join(names)
    if timestamps:
        new_filename += ".%s" % max(timestamps)
    
    new_filename += extension
    
    return os.path.join(path, new_filename)


CSS = 'css'
JS = 'js'

def has_optimizer(type_):
    if type_ == CSS:
        if getattr(settings, 'DJANGO_STATIC_YUI_COMPRESSOR', None):
            return True
        return slimmer is not None
    elif type_ == JS:
        if getattr(settings, 'DJANGO_STATIC_CLOSURE_COMPILER', None):
            return True
        if getattr(settings, 'DJANGO_STATIC_YUI_COMPRESSOR', None):
            return True
        
        return slimmer is not None
    else:
        raise ValueError("Invalid type %r" % type_)

def optimize(content, type_):
    if type_ == CSS:
        if getattr(settings, 'DJANGO_STATIC_YUI_COMPRESSOR', None):
            return _run_yui_compressor(content, type_)
        return css_slimmer(content)
    elif type_ == JS:
        if getattr(settings, 'DJANGO_STATIC_CLOSURE_COMPILER', None):
            return _run_closure_compiler(content)
        if getattr(settings, 'DJANGO_STATIC_YUI_COMPRESSOR', None):
            return _run_yui_compressor(content, type_)
        return js_slimmer(content)
    else:
        raise ValueError("Invalid type %r" % type_)
    
def _run_closure_compiler(jscode):
    
    cmd = "java -jar %s" % settings.DJANGO_STATIC_CLOSURE_COMPILER
    proc = Popen(cmd, shell=True, stdout=PIPE, stdin=PIPE, stderr=PIPE)
    (stdoutdata, stderrdata) = proc.communicate(jscode)
    if stderrdata:
        return "/* ERRORS WHEN RUNNING CLOSURE COMPILER\n" + stderrdata + '\n*/\n' + jscode
    
    return stdoutdata

def _run_yui_compressor(code, type_):
    
    cmd = "java -jar %s --type=%s" % (settings.DJANGO_STATIC_YUI_COMPRESSOR, type_)
    proc = Popen(cmd, shell=True, stdout=PIPE, stdin=PIPE, stderr=PIPE)
    (stdoutdata, stderrdata) = proc.communicate(code)
    if stderrdata:
        return "/* ERRORS WHEN RUNNING CLOSURE COMPILER\n" + stderrdata + '\n*/\n' + code
    
    return stdoutdata
