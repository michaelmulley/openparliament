OP.utils.formatJSON = function(content) {
    /* Takes a string of raw JSON, and returns escaped, syntax-highlighted
    HTML, with links in <a> tags. */
    var lines = content.split('\n');
    var l;
    var r = [];
    var structure = /^(\s*)([{}\[\]])(,?)\s*$/;
    for (var i = 0; i < lines.length; i++) {
        l = lines[i];
        var smatch = l.match(structure);
        if (smatch) {
            r.push(smatch[1] + '<span class="structure">' + smatch[2] + '</span>' + smatch[3]);
        }
        else {
            var match = l.match(/^(\s+)("[^"]+"): (.+?)(,?)\s*$/);
            if (!match) {
                r.push(l);
            }
            else {
                var val = match[1] + '<span class="key">' + _.escape(match[2])
                    + '</span>: ';
                if (structure.test(match[3])) {
                    val += '<span class="structure">' + _.escape(match[3]) + '</span>';
                }
                else {
                    val += '<span class="value">';
                    if (
                        (/url"$/.test(match[2]) || match[2] === '"next"' || match[2] == '"previous"')
                            && /^"(h|\/)/.test(match[3])) {
                        var url = match[3].substr(1, match[3].length - 2);
                        url = url.replace(/[?&]format=apibrowser/, '');
                        val += '"<a href="' + url;
                        if (url.substr(0, 1) === '/') {
                            if (url.indexOf('?') === -1) {
                                val += '?';
                            }
                            else {
                                val += '&';
                            }
                            val += 'format=apibrowser';
                        }
                        val += '">' + _.escape(url) + '</a>"';
                    }
                    else {
                        val += _.escape(match[3]).replace(/\\u2014/g, '&mdash;');
                    }
                    val += '</span>';
                }
                r.push(val + match[4]);
            }
        }
    }
    return r.join('\n');
};