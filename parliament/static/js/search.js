(function() {

    var visualSearch;

    var currentSort = '';

    OP.search = {

        triggerSearch: function(query) {
            var params = { q: query};
            if (currentSort) {
                params.sort = currentSort;
            }
            History.pushState(null, null, '/search/?' + $.param(params));
        },

        getQuery: function() {
            return visualSearch.searchQuery.serialize()
        },

        init: function(initialQuery) {
            visualSearch = VS.init({
                container: $('#visual_search'),
                query: initialQuery,
                callbacks: {
                    facetMatches: OP.search.VSfacetMatches,
                    valueMatches: OP.search.VSvalueMatches,
                    search: OP.search.triggerSearch
                }
            });

            $('a[data-add-facet]').click(function(e) {
                e.preventDefault();
                visualSearch.searchBox.addFacet($(this).attr('data-add-facet'));
            });

            var dateFilter = new OP.SearchDateFilter();
            $('#main_search_controls').append(dateFilter.$el);
            dateFilter.bind('sliderChange', function(values, fullRange) {
                var textVal = values[0] + ' to ' + values[1];
                var dateFacet = visualSearch.searchQuery.detect(function (f) {
                    return f.get('category') === 'Date';
                });
                if (fullRange) {
                    if (dateFacet) {
                        visualSearch.searchQuery.remove(dateFacet);
                        visualSearch.searchBox.renderFacets();
                    }
                }
                else {
                    if (dateFacet) {
                        dateFacet.set('value', textVal);
                    }
                    else {
                        visualSearch.searchBox.addFacet('Date', textVal);
                    }
                }
            });
            dateFilter.bind('sliderChangeCompleted', function() {
                OP.search.triggerSearch(OP.search.getQuery());
            });

            $(document).bind('op_search_results_loaded', function() {
                var $searchHeader = $('.search_header');
                if (!$searchHeader.length) { return dateFilter.setValues([0], [0]);}
                var chart_years = _.map($searchHeader.attr('data-years').split(','), function(y) { return parseInt(y, 10)});
                var chart_values = _.map($searchHeader.attr('data-values').split(','), function(y) { return parseInt(y, 10)});
                dateFilter.setValues(chart_years, chart_values);

                var dateFacet = visualSearch.searchQuery.detect(function (f) {
                    return f.get('category') === 'Date';
                });
                if (dateFacet) {
                    var sliderValues = _.map(dateFacet.get('value').split(' to '), function(d) {
                        d = d.split('-');
                        return parseInt(d[0], 10) * 12 + parseInt(d[1], 10) - 1;
                    });
                    dateFilter.setSliderValues(sliderValues);
                }
                else {
                    dateFilter.setSliderValues();
                }

                currentSort = $searchHeader.attr('data-sort');
            });

            $(window).bind('statechange', function() {
                var url = History.getState().url;
                var query = OP.utils.getQueryParam('q', url);
                if (query && url.indexOf('/search/?') !== -1) {
                    visualSearch.searchBox.value(query);
                }

            });

            $('#content').delegate('.sort_options a', 'click', function(e) {
                e.preventDefault();
                currentSort = $(this).attr('data-sort');
                OP.search.triggerSearch(OP.search.getQuery());
            });
        }
    };
})();

