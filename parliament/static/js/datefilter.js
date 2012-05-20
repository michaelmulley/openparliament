(function() {
    var dateFilterTemplate = _.template(
        '<div class="searchdatefilter" style="display:none">' +
            '<div class="chart" style="width: <%= width %>px; height: <%= chartHeight %>px;">' +
                '<div class="hover-label" style="display:none; height: <%= chartHeight %>px;">' +
                    '<div class="highlight"></div>' +
                    '<div class="label"><span class="date"></span><br><span class="value"></span><br><span class="note"></span></div>' +
                '</div>' +
            '</div>' +
            '<div class="tools_wrap"><div class="tools" style="display:none">' +
                '<div class="label-min"></div><div class="label-max"></div>' +
                '<div class="slider"></div>' +
            '</div></div>' +
        '</div>');

    OP.SearchDateFilter = function(opts) {
        opts = opts || {};
        _.defaults(opts, {
            width: 770,
            chartHeight: 85,
            strokeStyle: '#ff9900',
            fillStyle: '#e6f2fa',
            lineWidth: 3.5
        });
        _.extend(this, opts);

        var self = this;

        this.$el = $(dateFilterTemplate(this));

        var $chart = this.$el.find('.chart');
        $chart.mousemove(function(e) {
            self.updateChartLabel(e.pageX - $chart.offset().left);
        }).mouseleave(function(e) {
            self.$el.find('.hover-label').hide();
        });

        var $tools = this.$el.find('.tools');
        this.$el.hover(
            function(e) { $tools.show(); },
            function(e) { $tools.hide(); }
        );

    };

    _.extend(OP.SearchDateFilter.prototype, Backbone.Events, {

        setValues: function(dates, values) {
            this.dates = dates;
            this.values = values;

            if (_.max(values) === 0) {
                // No results, presumably.
                return this.$el.hide();
            }

            this.drawGraph();
            this.setSlider();
        },

        drawGraph: function() {
            var self = this;
            var ymin = Math.floor(_.min(this.values) * 0.8);
            var ymax = Math.ceil(_.max(this.values) * 1.1);
            var scaler = this.chartHeight / (ymax - ymin);
            var yvals = _.map(this.values, function(v) {
                return self.chartHeight - Math.round((v - ymin) * scaler);
            });
            var xvals = [];
            var i;
            for (i = 0; i < (this.values.length - 1); i++) {
                xvals.push(Math.floor(i * (this.width / (this.values.length - 1))));
            }
            xvals.push(this.width);

            var segmentInterval = Math.round((this.width / (this.values.length - 1)) / 2);
            this.xSegments = _.map(xvals, function(v) { return v - segmentInterval; });
            this.xSegments[0] = 0
            this.xSegments.push(xvals[xvals.length-1]);

            this.$el.show();

            this.$el.find('.label-min').text(this.dates[0].toString());
            this.$el.find('.label-max').text(this.dates[this.dates.length-1].toString());

            if (!this.canvasContext) {
                // Initialize the canvas. We do it in this slightly laborious way
                // because, well, it works in IE.
                var canvas = document.createElement('canvas');
                canvas.width = this.width;
                canvas.height = this.chartHeight;
                this.$el.find('.chart').prepend(canvas);
                if (window.G_vmlCanvasManager) {
                    // Initialize IE 7-8 canvas shim
                    window.G_vmlCanvasManager.initElement(canvas);
                }
                this.canvasContext = canvas.getContext('2d');
            }

            var ctx = this.canvasContext;

            ctx.clearRect(0, 0, this.width, this.chartHeight);

            ctx.beginPath();
            ctx.strokeStyle = this.strokeStyle;
            ctx.fillStyle = this.fillStyle;
            ctx.lineWidth = this.lineWidth;
            ctx.moveTo(xvals[0], yvals[0]);
            for (i = 1; i < xvals.length; i++) {
                ctx.lineTo(xvals[i], yvals[i]);
            }
            ctx.stroke();
            ctx.lineTo(this.width, this.chartHeight);
            ctx.lineTo(0, this.chartHeight);
            ctx.lineTo(xvals[0], yvals[0]);
            ctx.fill();
            ctx.closePath();

        },

        updateChartLabel: function(xCoord) {
            if (!this.xSegments) { return; }
            for (var i = this.xSegments.length - 2; i >= 0; i--) {
                if (xCoord >= this.xSegments[i]) {
                    break;
                }
            }

            var segmentRange = [this.xSegments[i], this.xSegments[i+1]];
            var date = this.dates[i];
            var dateCount = this.values[i];
            var dateCountLabel
            if (dateCount === 1) {
                dateCountLabel = 'One result';
            }
            else if (dateCount === 0) {
                dateCountLabel = 'No results';
            }
            else {
                dateCountLabel = dateCount + ' results'
            }

            this.$el.find('.hover-label .label .date').text(date);
            this.$el.find('.hover-label .label .value').text(dateCountLabel);
            this.$el.find('.hover-label').css({
                left: segmentRange[0],
                width: segmentRange[1] - segmentRange[0]
            }).show();
        },

        setSlider: function() {
            var $slider = this.$el.find('.slider');

            var opts = {
                min: this.dates[0],
                max: this.dates[this.dates.length-1],
                range: true
            };
            opts.values = [opts.min, opts.max];

            if (!this.sliderInit) {
                this.sliderInit = true;
                var self = this;
                opts.slide = function (e, ui) {
                    var sv = ui.values;
                    if (!self.sliderValues || sv[0] !== self.sliderValues[0] || sv[1] !== self.sliderValues[1]) {
                        self.sliderValues = sv.slice(0);
                        var fullRange = (sv[0] === opts.min && sv[1] === opts.max);
                        self.trigger('sliderChange', sv, fullRange)
                    }
                };
                opts.start = function (e, ui) {
                    self.slideStartValues = ui.values.slice(0);
                };
                opts.stop = function (e, ui) {
                    if (!self.slideStartValues
                            || ui.values[0] !== self.slideStartValues[0]
                            || ui.values[1] !== self.slideStartValues[0]) {
                        self.trigger('sliderChangeCompleted', ui.values);
                    }
                };
                $slider.slider(opts);
            }
            else {
                var fullRange = (
                    $slider.slider('option', 'min') === $slider.slider('values', 0) &&
                    $slider.slider('option', 'max') === $slider.slider('values', 1)
                );
                if (this.sliderValues && !fullRange) {
                    opts.values = this.sliderValues;
                }
                if (opts.values[0] < opts.min) {
                    opts.values[0] = opts.min;
                }
                if (opts.values[1] < opts.min) {
                    opts.values[1] = opts.min;
                }
                $slider.slider('option', opts);
            }
        }

    });

})();