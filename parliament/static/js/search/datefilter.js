(function() {
    var APmonths = ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.'];

    var dateFilterTemplate = _.template(
        '<div class="searchdatefilter" style="display:none">' +
            '<div class="chart" style="width: 100%; height: <%= chartHeight %>px;">' +
                '<div class="hover-label" style="display:none; height: <%= chartHeight %>px;">' +
                    '<div class="highlight"></div>' +
                    '<div class="label"><span class="date"></span><br><span class="value"></span><br><span class="note"></span></div>' +
                '</div>' +
            '</div>' +
            '<div class="tools">' +
                '<div class="label left"><span></span></div><div class="label right"><span></span></div>' +
                '<div class="slider"></div>' +
            '</div>' +
        '</div>');

    OP.SearchDateFilter = function(opts) {
        opts = opts || {};
        _.defaults(opts, {
            chartHeight: 75,
            strokeStyle: '#ff9900',
            fillStyle: '#e6f2fa',
            lineWidth: 3.5,
            valueToDate: function(v) {
                return Math.floor(v/12) + '-' + (v % 12 < 9 ? '0' : '') + ((v % 12) + 1);
            },
            valueToLabel: function(v) {
                return APmonths[v % 12] + ' ' + Math.floor(v/12);
            },
            currentYear: new Date().getFullYear(),
            currentMonth: new Date().getMonth()
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

        this.$el.find('.hover-label .highlight').click(function(e) {
            var year = parseInt(self.$el.find('.hover-label .date').text(), 10);
            self.setSliderValues([year * 12, (year * 12) + 11], true);
        });

        var $tools = this.$el.find('.tools');
        $tools.css({opacity: 0.4});
        this.$el.hover(
            function(e) { $tools.fadeTo(200, 1.0); },
            function(e) { $tools.fadeTo(200, 0.4); }
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

            this.$el.show();
            var chart_width = this.$el.width();

            this.xSegments = [0];
            for (i = 1; i < (this.values.length); i++) {
                this.xSegments.push(this.xSegments[i-1] + 12);
            }
            this.xSegments.push(this.xSegments[this.xSegments.length-1] + this.currentMonth + 1);
            var xScaler = chart_width / this.xSegments[this.xSegments.length-1];
            this.xSegments = _.map(this.xSegments, function(x) {
                return Math.round(x * xScaler)
            });

            xvals = [0];
            for (i = 1; i < (this.values.length - 1); i++) {
                xvals.push(this.xSegments[i] +
                    Math.round((this.xSegments[i+1] - this.xSegments[i]) / 2));
            }
            xvals.push(chart_width);


            if (!this.canvasContext) {
                // Initialize the canvas. We do it in this slightly laborious way
                // because, well, it works in IE.
                var canvas = document.createElement('canvas');
                canvas.width = chart_width;
                canvas.height = this.chartHeight;
                this.$el.find('.chart').prepend(canvas);
                this.canvasContext = canvas.getContext('2d');
            }

            var ctx = this.canvasContext;

            ctx.clearRect(0, 0, chart_width, this.chartHeight);

            ctx.beginPath();
            ctx.strokeStyle = this.strokeStyle;
            ctx.fillStyle = this.fillStyle;
            ctx.lineWidth = this.lineWidth;
            ctx.moveTo(xvals[0], yvals[0]);
            for (i = 1; i < xvals.length; i++) {
                ctx.lineTo(xvals[i], yvals[i]);
            }
            ctx.stroke();
            ctx.lineTo(chart_width, this.chartHeight);
            ctx.lineTo(0, this.chartHeight);
            ctx.lineTo(xvals[0], yvals[0]);
            ctx.fill();
            ctx.closePath();

            if (this.discontinuity) {
                var idx = _.indexOf(this.dates, this.discontinuity);
                if (idx !== -1) {
                    var discx = this.xSegments[idx];
                    ctx.beginPath();
                    ctx.lineWidth = 0.5;
                    ctx.strokeStyle = '#888888'
                    ctx.moveTo(discx, 0);
                    for (var y = 0; y < this.chartHeight; y++) {
                        if (y % 6 < 4) {
                            ctx.moveTo(discx, y);
                        }
                        else {
                            ctx.lineTo(discx, y);
                        }
                    }
                    ctx.stroke();
                    ctx.closePath();

                }
            }

        },

        updateChartLabel: function(xCoord) {
            if (!this.xSegments) { return; }
            for (var i = this.xSegments.length - 2; i >= 0; i--) {
                if (xCoord >= this.xSegments[i]) {
                    break;
                }
            }

            if (i < 0) {
                return;
            }

            var segmentRange = [this.xSegments[i], this.xSegments[i+1]];
            var date = this.dates[i];
            var dateCount = this.values[i];
            var dateCountLabel;
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
            this.$el.find('.hover-label .label .note').text(
                date === this.discontinuity ? this.discontinuityNote : ''
            );
            this.$el.find('.hover-label').css({
                left: segmentRange[0],
                width: segmentRange[1] - segmentRange[0]
            }).show();
        },

        setSlider: function() {
            var $slider = this.$el.find('.slider');

            var maxPossDate = (this.currentYear * 12) + this.currentMonth;

            var opts = {
                min: this.dates[0] * 12,
                max: _.min([(this.dates[this.dates.length-1] * 12) + 11, maxPossDate]),
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
                        self.updateSliderLabels(sv);
                        self.trigger('sliderChange', _.map(sv, self.valueToDate), fullRange)
                    }
                };
                opts.start = function (e, ui) {
                    self.slideStartValues = ui.values.slice(0);
                };
                opts.stop = function (e, ui) {
                    if (!self.slideStartValues
                            || ui.values[0] !== self.slideStartValues[0]
                            || ui.values[1] !== self.slideStartValues[0]) {
                        self.trigger('sliderChangeCompleted', _.map(ui.values, self.valueToDate));
                    }
                    self.updateSliderLabels(ui.values);
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
            this.updateSliderLabels(opts.values)
        },

        updateSliderLabels: function(values) {
            var $left = this.$el.find('.tools .label.left');
            var $right = this.$el.find('.tools .label.right');

            $left.position({
                my: ((values[1] - values[0]) < 24) ? "right top" : "left top",
                at: "center bottom",
                of: this.$el.find('.ui-slider-handle')[0],
                collision: "fit"
            }).find('span').text(this.valueToLabel(values[0]));

            if (values[0] === values[1]) {
                $right.hide();
            }
            else {
                $right.position({
                    my: "left top",
                    at: "center bottom",
                    of: this.$el.find('.ui-slider-handle')[1],
                    collision: "fit"
                }).show().find('span').text(this.valueToLabel(values[1]));
            }

        },

        setSliderValues: function(values, triggerEvent) {
            if (!this.sliderInit) { return; }
            var $slider = this.$el.find('.slider');
            var limits = [$slider.slider('option', 'min'), $slider.slider('option', 'max')];
            if (values) {
                values = [_.max([values[0], limits[0]]), _.min([values[1], limits[1]])];
            }
            else {
                values = limits;
            }
            $slider.slider('option', {values: values});
            this.sliderValues = values;
            this.updateSliderLabels(values);
            if (triggerEvent) {
                var formatted = _.map(values, this.valueToDate);
                this.trigger('sliderChange', formatted);
                this.trigger('sliderChangeCompleted', formatted);
            }
        }

    });

})();