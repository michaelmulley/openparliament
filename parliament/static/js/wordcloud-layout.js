// Lay out an SVG wordcloud
// The code draws heavily from https://github.com/jasondavies/d3-cloud

OP.wordcloud = {
	defaultOpts: {
		size: [null, 175],
		font: '"Helvetica Neue", Helvetica, sans serif',
		weight: 'bold',
		padding: '0.5',
		appendTo: '.wordcloud'
	},
	colors: "#1f77b4 #ff7f0e #2ca02c #d62728 #9467bd #8c564b #e377c2 #7f7f7f #bcbd22 #17becf".split(' '),
	sizeOptions: {
		outputRange: [16,80],
		1: {
			range: [0.8, 6]
		},
		2: {
			range: [0.2, 2]
		},
		3: {
			range: [0.1, 2]
		}
	}
};
OP.wordcloud.linearScale = function(n, inputRange, outputRange) {
	var normalized = Math.min(Math.max(n - inputRange[0], 0), inputRange[1]) /
		(inputRange[1] - inputRange[0]);
    return Math.round(normalized * (outputRange[1] - outputRange[0])) + outputRange[0];
};
OP.wordcloud.logScale = function(n, inputRange, outputRange) {
	return OP.wordcloud.linearScale(
		Math.log(n/inputRange[0]),
		[0, Math.log(inputRange[1] / inputRange[0])],
		outputRange
	);
};
OP.wordcloud.calculate = function(words, opts) {

	var prepareWord = function(word) {
		word.num_words = word.text.split(' ').length;
		word.size = OP.wordcloud.logScale(word.score,
			OP.wordcloud.sizeOptions[word.num_words].range,
			OP.wordcloud.sizeOptions.outputRange);
	};

	var go = function() {
		var board = [];
		var i = 0;
		var bounds = null;

		// Zero the board
		var boardLength = (opts.size[0] >> 5) * opts.size[1];
		for (i = 0; i < boardLength; i++) {
			board[i] = 0;
		}

		_.each(words, prepareWord);
		// Sort by declining size
		words.sort(function(a, b) {
			return b.size - a.size;
		});

		var start = +new Date;

		var doWord = function(word) {
			if (placeWord(word, board, bounds)) {
				if (bounds) {
					expandBounds(bounds, word);
				}
				else {
					bounds = [{x: word.x + word.x0, y: word.y + word.y0}, {x: word.x + word.x1, y: word.y + word.y1}];
				}
				// word.x -= opts.size[0] >> 1;
				// word.y -= opts.size[1] >> 1;
				if (opts.onWord) opts.onWord(word);
			}
		};

		var word = null;
		i = 0;
		var step = function() {
			if (i >= words.length) {
				// console.log(+new Date - start);
				return;
			}
			word = words[i];
			doWord(word);
			i += 1;
			if (opts.async && i % 2 === 1) {
				_.defer(step);
			}
			else {
				step();
			}
		};

		step();

		return words;
	};


	var placeWord = function(word, board, bounds) {
		if (word.placed) return true;
		getTextSprite(word);

		// Pick a starting spot
		word.x = (opts.size[0] * (Math.random() + 0.5)) >> 1;
		word.y = (opts.size[1] * (Math.random() + 0.5)) >> 1;

		var perimeter = [{x: 0, y: 0}, {x: opts.size[0], y: opts.size[1]}],
			startX = word.x,
			startY = word.y,
			maxDelta = Math.sqrt(opts.size[0] * opts.size[0] + opts.size[1] * opts.size[1]),
			s = spiral(opts.size),
			dt = Math.random() < 0.5 ? 1 : -1,
			t = -dt,
			dxdy,
			dx,
			dy;

		while (dxdy = s(t += dt)) {
			dx = ~~dxdy[0];
			dy = ~~dxdy[1];

			if (Math.min(dx, dy) > maxDelta) break;

			word.x = startX + dx;
			word.y = startY + dy;

			if (word.x + word.x0 < 0 || word.y + word.y0 < 0 ||
					word.x + word.x1 > opts.size[0] || word.y + word.y1 > opts.size[1]) continue;
			// TODO only check for collisions within current bounds.
			if (!bounds || !collide(word, board, opts.size[0])) {
				if (!bounds || collideRects(word, bounds)) {
					var sprite = word.sprite,
							w = word.width >> 5,
							sw = opts.size[0] >> 5,
							lx = word.x - (w << 4),
							sx = lx & 0x7f,
							msx = 32 - sx,
							h = word.y1 - word.y0,
							x = (word.y + word.y0) * sw + (lx >> 5),
							last;
					for (var j = 0; j < h; j++) {
						last = 0;
						for (var i = 0; i <= w; i++) {
							board[x + i] |= (last << msx) | (i < w ? (last = sprite[j * w + i]) >>> sx : 0);
						}
						x += sw;
					}
					delete word.sprite;
					word.placed = true;
					return true;
				}
			}
		}
		if (word.size > 9) {
			word.size = Math.max(8, word.size - 6);
			delete word.sprite;
			getTextSprite(word);
			return placeWord(word, board, bounds);
		}
		return false;
	};

	var spiral = function(size) {
		// Archimedean
		var e = size[0] / size[1];
		return function(t) {
			return [e * (t *= 0.1) * Math.cos(t), t * Math.sin(t)];
		};
	};

	var collide = function(tag, board, sw) {
		sw >>= 5;
		var sprite = tag.sprite,
				w = tag.width >> 5,
				lx = tag.x - (w << 4),
				sx = lx & 0x7f,
				msx = 32 - sx,
				h = tag.y1 - tag.y0,
				x = (tag.y + tag.y0) * sw + (lx >> 5),
				last;
		for (var j = 0; j < h; j++) {
			last = 0;
			for (var i = 0; i <= w; i++) {
				if (((last << msx) | (i < w ? (last = sprite[j * w + i]) >>> sx : 0))
						& board[x + i]) return true;
			}
			x += sw;
		}
		return false;
	};

	var collideRects = function(a, b) {
		return a.x + a.x1 > b[0].x && a.x + a.x0 < b[1].x && a.y + a.y1 > b[0].y && a.y + a.y0 < b[1].y;
	};

	var expandBounds = function(bounds, d) {
		var b0 = bounds[0],
				b1 = bounds[1];
		if (d.x + d.x0 < b0.x) b0.x = d.x + d.x0;
		if (d.y + d.y0 < b0.y) b0.y = d.y + d.y0;
		if (d.x + d.x1 > b1.x) b1.x = d.x + d.x1;
		if (d.y + d.y1 > b1.y) b1.y = d.y + d.y1;
	};


	var canvas = document.createElement('canvas');
	// Find pixel resolution of canvas
	canvas.width = 1;
	canvas.height = 1;
	var cc = canvas.getContext("2d", {willReadFrequently: true});
	var canvas_ratio = Math.sqrt(cc.getImageData(0, 0, 1, 1).data.length >> 2);
	var canvas_dim = canvas.height = canvas.width = 2048 / canvas_ratio;
	cc.fillStyle = cc.strokeStyle = "red";
	cc.textAlign = "center";

	var getTextSprite = function(word) {
		if (word.sprite) return;
		cc.clearRect(0, 0, canvas.width, canvas.height);

		cc.save();
		cc.font = (opts.style || '') + opts.weight + " " + Math.floor((word.size + 1) / canvas_ratio) + "px " + opts.font;
		var w = cc.measureText(word.text +"m").width * canvas_ratio;
		var h = Math.floor(word.size * 2); 
		w = (w + 31) >> 5 << 5; // snap to nearest 32

		// FIXME switch to next line
		var x = 0, y = 0;
		cc.translate((x + (w >> 1)) / canvas_ratio, (y + (h >> 1)) / canvas_ratio); // not sure what the bitshift is doing
		cc.fillText(word.text, 0, 0);
		if (opts.padding) {
			cc.lineWidth = 2 * opts.padding;
			cc.strokeText(word.text, 0, 0);
		}
		cc.restore();

		word.width = w;
		word.height = h;
		word.canvas_xoff = x;
		word.canvas_yoff = y;
		word.x1 = w >> 1;
		word.y1 = h >> 1;
		word.x0 = -word.x1;
		word.y0 = -word.y1;

		var maxWidth = w;
		var maxHeight = h;

		// maxHeight = maxWidth = canvas_dim;

		var pixels = cc.getImageData(0, 0, maxWidth, maxHeight).data;
		var sprite = [];
		var w32 = w >> 5;

		for (var i = 0; i < h * w32; i++) sprite[i] = 0;
		x = word.canvas_xoff;
		y = word.canvas_yoff;
		var seen = 0;
		var seenRow = -1;
		for (var j = 0; j < h; j++) {
			for (var i = 0; i < w; i++) {
				var k = w32 * j + (i >> 5),
						m = pixels[((y + j) * maxWidth + (x + i)) << 2] ? 1 << (31 - (i % 32)) : 0;
				sprite[k] |= m;
				seen |= m;
			}
			if (seen) seenRow = j;
			else {
				word.y0++;
				h--;
				j--;
				y++;
			}
		}
		word.y1 = word.y0 + seenRow;
		word.sprite = sprite.slice(0, (word.y1 - word.y0) * w32);

	};

	if (opts.async) {
		_.delay(go, 1);
	}
	else {
		return go();
	}

};

OP.wordcloud.drawSVG = function(words, opts) {
	opts = opts || {};

	_.defaults(opts, OP.wordcloud.defaultOpts);

	if (!words || !words.length) return;

	var test_svg = function() {
		return !!document.createElementNS && !!document.createElementNS('http://www.w3.org/2000/svg', 'svg').createSVGRect;
	};

	var test_canvas = function() {
		var elem = document.createElement('canvas');
		return !!(elem.getContext && elem.getContext('2d') && typeof elem.getContext('2d').fillText == 'function');
	};

	if (!test_svg() || !test_canvas()) return false;

	if (!opts.size[0]) {
		// Calculate width
		if (opts.appendTo) {
			opts.size[0] = $(opts.appendTo).width();
		}
		else {
			opts.size[0] = 960;
		}
	}

	var g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
	var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
	svg.setAttribute('width', opts.size[0]);
	svg.setAttribute('height', opts.size[1]);
	// svg.setAttribute('transform', "translate(" + [opts.size[0] / 2, opts.size[1] / 2] + ")");

	if (opts.searchURL) {
		$(svg).delegate('text', 'mouseenter', function(e) {
			this.setAttribute('fill-opacity', 0.8);
		}).delegate('text', 'mouseleave', function(e) {
			this.setAttribute('fill-opacity', 1);
		}).delegate('text', 'click', function(e) {
			document.location.href = opts.searchURL + encodeURIComponent('"' + $(this).text() + '"');
		});
	}

	svg.appendChild(g);

	var addWord = function(word) {
		var t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
		t.setAttribute('style', "font-size: " + word.size + "px; font-family: " + opts.font
			+ "; font-weight: " + opts.weight + "; fill: " + _.sample(OP.wordcloud.colors) + ";");
		t.setAttribute('text-anchor', 'middle');
		t.setAttribute('transform', "translate(" + [word.x, word.y] + ")");
		if (opts.searchURL) t.setAttribute('cursor', 'pointer');
		$(t).text(word.text);
		g.appendChild(t);
	};

	opts.onWord = addWord;
	opts.async = true;

	OP.wordcloud.calculate(words, opts);

	if (opts.appendTo) {
		$(opts.appendTo).append(svg);
	}

	return svg;
};
