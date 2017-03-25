(function(){

    var facetTemplate = _.template(
        "<% for (var ftype = 0; ftype < data.length; ftype++) { if (data[ftype].values.length > 1) { %>" +
            '<div class="facetgroup"><% for (var row = 0; row < data[ftype].values.length; row++) { if (data[ftype].labels[row]) { %>' +
                '<div class="item<% if (row >= collapseAfter) { print(" collapsed"); } %>">' +
                    '<div class="barbg <%- OP.utils.slugify(data[ftype].values[row]) %>" style="width: <%= Math.round((data[ftype].counts[row]/data[ftype].max) * 100) %>%"></div>' +
                    '<div class="label"><em><%- data[ftype].counts[row] %></em><a href="#" data-add-facet="<%- data[ftype].filterName %>" data-facet-value="<%- data[ftype].values[row] %>"><%- data[ftype].labels[row] %></a></div>' +
                '</div><% } } %>' +
            '<% if (data[ftype].values.length > collapseAfter) { %>' +
                '<div class="item show-more"><div class="label"><a href="#" class="quiet">more <%- data[ftype].pluralName.toLowerCase() %> &rarr;</a></div></div>' +
            '<% } %>' +
            '</div>' +
         '<% } } %>'
    );

    OP.FacetWidget = function(opts) {
        opts = opts || {};
        _.defaults(opts, {
            collapseAfter: 4
        });
        _.extend(this, opts);
        this.$el = $('<div class="facetwidget"></div>');

        this.$el.on('click', '.show-more a', function(e) {
            e.preventDefault();
            $(this).closest('.facetgroup').addClass('nocollapse');
        });
    };

    OP.FacetWidget.prototype.setValues = function(data) {
        this.data = data;
        var self = this;
        _.each(data, function(f) {
            f.counts = _.filter(f.rawValues, _.isNumber);
            f.values = _.filter(f.rawValues, _.isString);
            if (f.labelFunc) {
                f.labels = _.map(f.values, f.labelFunc);
            }
            else {
                f.labels = f.values;
            }
            f.max = _.max(f.counts);
        });
        this.render();
    };

    OP.FacetWidget.prototype.render = function() {
        this.$el.html(facetTemplate(this));
    };

})();