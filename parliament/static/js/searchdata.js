(function () {

    var accache = {};

    if (!OP.search) { OP.search = {};}

    OP.search.VSfacetMatches = function(callback) {
        callback([
            'MP', 'Party', 'Committee', 'Province', 'Type'
        ]);
    };

    OP.search.VSvalueMatches = function(facet, searchTerm, callback) {
        switch (facet) {
            case 'Year':
                callback([
                    '1994','1995','1996','1997','1998','1999','2000','2001',
                    '2002','2003','2004','2005','2006','2007','2008','2009',
                    '2010','2011','2012'
                ], {preserveOrder: true});
                break;
            case 'MP':
//            case 'Person':
                $.getJSON('/politicians/autocomplete/?' + $.param({q: searchTerm}), function (data) {
                    callback(data.content);
                });
                break;
            case 'Party':
                callback([
                    {value: 'Conservative', label: 'Conservative'},
                    {value: 'Liberal', label: 'Liberal'},
                    {value: 'NDP', label: 'NDP'},
                    {value: 'Bloc', label: 'Bloc Québécois'},
                    {value: 'Green', label: 'Green'},
                    {value: 'Progressive Conservative', label: 'Progressive Conservative'},
                    {value: 'Reform', label: 'Reform'},
                    {value: 'Canadian Alliance', label: 'Canadian Alliance'},
                    {value: 'Independent', label: 'Independent'}
                ], {preserveOrder: true});
                break;
            case 'Province':
                callback([
                    'AB',
                    'BC',
                    'MB',
                    'NB',
                    'NL',
                    'NS',
                    'NT',
                    'NU',
                    'ON',
                    'PE',
                    'QC',
                    'SK',
                    'YK'
                ], {preserveOrder: true});
                break;
            case 'Committee':
                if (accache.committees) {
                    return callback(accache.committees, {preserveOrder: true});
                }
                $.getJSON('/committees/?format=json&limit=100', function(data) {
                    accache.committees = _.map(data.objects, function(i) { 
                        return {
                            value: i.slug,
                            label: i.name.en
                        };
                    });
                    callback(accache.committees, {preserveOrder: true});
                });
                break;
            case 'Type':
                callback([
                    {label: 'Speech (House debate)', value: 'debate'},
                    {label: 'Speech (Committee meeting)', value: 'committee'},
                    {label: 'Bill', value: 'bill'}
                ]);
                break;
        }
    };

    OP.PROVINCES = {
        BC: 'B.C.',
        AB: 'Alberta',
        MB: 'Manitoba',
        SK: 'Saskatchewan',
        ON: 'Ontario',
        QC: 'Qu\u00e9bec',
        NB: 'New Brunswick',
        PE: 'P.E.I.',
        NS: 'Nova Scotia',
        NL: 'Newfoundland',
        NT: 'N.W.T.',
        YT: 'Yukon',
        NU: 'Nunavut'
    };

    OP.search.DOCTYPES = {
        debate: 'House debate',
        committee: 'Committee meeting',
        mp: 'Person',
        bill: 'Bill'
    };
    
})();