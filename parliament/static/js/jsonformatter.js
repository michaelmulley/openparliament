OP.utils.formatJSON = function(content) {
    /* Takes a string of raw JSON, and returns escaped, syntax-highlighted
    HTML, with links in <a> tags. */

    var format_value = function(v) {
        var r = '<span class="value">';
        if (/^"(http:|\/)\S+"$/.test(v)) {
            // Looks like a URL
            var url = v.substr(1, v.length - 2);
            r += '&quot;<a href="' + url + '">' + _.escape(url) + '</a>&quot;';
        }
        else {
            r += _.escape(v).replace(/\\u2014/g, '&mdash;');
        }
        r += '</span>';
        return r;
    };

    var lines = content.split('\n');
    var l, match;
    var r = [];
    var structure = /^(\s*)([{}\[\]])(,?)\s*$/;
    for (var i = 0; i < lines.length; i++) {
        l = lines[i];
        var smatch = l.match(structure);
        if (smatch) {
            r.push(smatch[1] + '<span class="structure">' + smatch[2] + '</span>' + smatch[3]);
        }
        else {
            if (!(match = l.match(/^(\s+)("[^"]+"): (.+?)(,?)\s*$/))) {
                if (match = l.match(/^(\s+)("[^"]+")(,?)\s*$/)) {
                    r.push(match[1] + format_value(match[2]) + match[3]);
                }
                else {
                    r.push(l);
                }
            }
            else {
                var val = match[1] + '<span class="key">' + _.escape(match[2])
                    + '</span>: ';
                if (structure.test(match[3])) {
                    val += '<span class="structure">' + _.escape(match[3]) + '</span>';
                }
                else {
                    val += format_value(match[3]);
                }
                r.push(val + match[4]);
            }
        }
    }
    return r.join('\n');
};