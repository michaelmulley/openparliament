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
            window.history.pushState(null, null, url);
            OP.AJAXNavigate(url);
        },

        getQuery: function() {
            return visualSearch.searchQuery.serialize();
        },

        findFacet: function(name) {
            return visualSearch.searchQuery.detect(function (f) {
                return f.get('category') === name;
            });
        },

        createAlert: function() {
            var query = OP.search.getQuery();
            $.ajax({
                type: 'POST',
                url: '/alerts/create/',
                data: {query: query},
                dataType: 'json',
                success: function(data) {
                    if (data.status == 'ok') {
                        OP.utils.notify("Your alert has been created for " + query + ".", "success");
                    }
                }
            });
        },

        init: function(initialQuery) {

            /* Initialize VisualSearch widget */
            visualSearch = VS.init({
                container: $('#visual_search'),
                query: initialQuery,
                showFacets: false,
                callbacks: {
                    // facetMatches: OP.search.VSfacetMatches,
                    valueMatches: OP.search.VSvalueMatches,
                    search: OP.search.triggerSearch
                }
            });

            /* Hook up facet-editing links */
            $('#main_search_controls, #search_leftbar').on('click', 'a[data-add-facet]', function(e) {
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

            $('#search_leftbar_toggler').click(function(e) {
                e.preventDefault();
                $('#search_leftbar').slideToggle();
                $(this).find('li').toggleClass('is-active');
            });

            /* Initialize alert button */
            $('#add_alert button').click(OP.search.createAlert);

            /* Initialize facet widget */
            var facetWidget = new OP.FacetWidget();
            $('#search_leftbar').append(facetWidget.$el);

            /* Initialize date widget */
            var dateFilter = new OP.SearchDateFilter({
                discontinuityNote: "Our committee data starts in 2006, so there's often a spike here."
            });
            $('#search_content').prepend(dateFilter.$el);
            dateFilter.on('sliderChange', function(values, fullRange) {
                var textVal = values[0] + ' to ' + values[1];
                var dateFacet = OP.search.findFacet('Date');
                if (OP.search.findFacet('Document')) {
                    visualSearch.searchQuery.remove(OP.search.findFacet('Document'));
                }
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
            dateFilter.on('sliderChangeCompleted', function() {
                OP.search.triggerSearch();
            });

            /* Event on result loading */
            $(document).on('op_search_results_loaded', function(e, data) {

                if (data && data.facets) {
                    facetWidget.setValues(data.facets);
                }

                /* Display alert widget */
                if (OP.search.getQuery().length) {
                    $('#add_alert').show();
                }
                else {
                    $('#add_alert').hide();
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
            $(window).on('popstate', function() {
                var url = document.location.href;
                var query = OP.utils.getQueryParam('q', url);
                if (query && url.indexOf('/search/?') !== -1) {
                    visualSearch.searchBox.value(query);
                }

            });

            /* Sort links */
            $('#content').on('click', '.sort_options a', function(e) {
                e.preventDefault();
                currentSort = $(this).attr('data-sort');
                OP.search.triggerSearch(OP.search.getQuery());
            });
        }
    };
})();