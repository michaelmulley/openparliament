(function() {

    var visualSearch;

    var currentSort = '';

    OP.search = {

        triggerSearch: function(query) {
            if (_.isUndefined(query)) {
                query = OP.search.getQuery();
            }
            var params = { q: query };
            if (currentSort) {
                params.sort = currentSort;
            }
            var url = '/search/?' + $.param(params);
            History.pushState(null, null, url);
        },

        getQuery: function() {
            return visualSearch.searchQuery.serialize()
        },

        findFacet: function(name) {
            return visualSearch.searchQuery.detect(function (f) {
                return f.get('category') === name;
            });
        },

        init: function(initialQuery) {

            /* Initialize VisualSearch widget */
            visualSearch = VS.init({
                container: $('#visual_search'),
                query: initialQuery,
                callbacks: {
                    facetMatches: OP.search.VSfacetMatches,
                    valueMatches: OP.search.VSvalueMatches,
                    search: OP.search.triggerSearch
                }
            });

            /* Hook up facet-editing links */
            $('#main_search_controls, #search_leftbar').delegate('a[data-add-facet]', 'click', function(e) {
                e.preventDefault();
                var value = $(this).attr('data-facet-value');
                var facetName = $(this).attr('data-add-facet');

                var facetGroup = ['Person', 'MP', 'Witness']; // these are all people filters
                if (_.indexOf(facetGroup, facetName) !== -1) {
                    // get rid of the similar filters
                    _.each(_.without(facetGroup, facetName), function(fn) {
                        var ef = OP.search.findFacet(fn);
                        if (ef) {
                            visualSearch.searchQuery.remove(ef);
                        }
                    });
                }

                var existingFacet = OP.search.findFacet(facetName);
                if (existingFacet) {
                    if (value) {
                        existingFacet.set('value', value);
                    }
                    else {
                        visualSearch.searchQuery.remove(existingFacet);
                        visualSearch.searchBox.addFacet(facetName);
                    }
                }
                else {
                    visualSearch.searchBox.addFacet(facetName, value);
                }
                if (value) {
                    OP.search.triggerSearch();
                }
            });

            /* Initialize facet widget */
            var facetWidget = new OP.FacetWidget();
            $('#search_leftbar').append(facetWidget.$el);

            /* Initialize date widget */
            var dateFilter = new OP.SearchDateFilter({
                discontinuityNote: "Our committee data starts in 2006, so there's often a spike here."
            });
            $('#search_content').prepend(dateFilter.$el);
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
                OP.search.triggerSearch();
            });

            /* Event on result loading */
            $(document).bind('op_search_results_loaded', function(e, data) {

                if (data && data.facets) {
                    facetWidget.setValues(data.facets);
                }

                /* Set values in date widget */
                var $searchHeader = $('.search_header');
                if (!$searchHeader.length) { return dateFilter.setValues([0], [0]);}
                var chart_years = _.map($searchHeader.attr('data-years').split(','), function(y) { return parseInt(y, 10)});
                var chart_values = _.map($searchHeader.attr('data-values').split(','), function(y) { return parseInt(y, 10)});
                dateFilter.discontinuity = parseInt($searchHeader.attr('data-discontinuity'), 10);
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

            /* Update search box on back button */
            $(window).bind('statechange', function() {
                var url = History.getState().url;
                var query = OP.utils.getQueryParam('q', url);
                if (query && url.indexOf('/search/?') !== -1) {
                    visualSearch.searchBox.value(query);
                }

            });

            /* Sort links */
            $('#content').delegate('.sort_options a', 'click', function(e) {
                e.preventDefault();
                currentSort = $(this).attr('data-sort');
                OP.search.triggerSearch(OP.search.getQuery());
            });
        }
    };
})();

