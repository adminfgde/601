/* Matrix-style code rain background */
(function() {
  'use strict';
  var canvas = document.createElement('canvas');
  canvas.id = 'code-rain';
  document.body.prepend(canvas);

  var ctx = canvas.getContext('2d');
  var W, H, columns, drops = [];

  var chars = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789$%#@&()[]{}<>/*-+=~|;:.,_';
  // Also include some Chinese chars
  chars += '环境规划管理地理信息毒理学系统数据空间分析污染防治生态保护资源可持续';

  function resize() {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
    columns = Math.floor(W / 20);
    drops = [];
    for (var i = 0; i < columns; i++) {
      drops[i] = Math.floor(Math.random() * -H / 20);
    }
  }

  function draw() {
    ctx.fillStyle = 'rgba(13, 17, 23, 0.05)';
    ctx.fillRect(0, 0, W, H);

    ctx.fillStyle = '#58a6ff';
    ctx.font = '15px monospace';

    for (var i = 0; i < columns; i++) {
      var char = chars[Math.floor(Math.random() * chars.length)];
      var x = i * 20;
      var y = drops[i] * 20;

      // Gradient: brighter at top, dimmer at bottom
      var brightness = Math.max(0, 1 - (drops[i] * 20) / H * 0.8);
      ctx.fillStyle = 'rgba(88, 166, 255, ' + (0.3 + brightness * 0.7) + ')';
      ctx.fillText(char, x, y);

      if (y > H && Math.random() > 0.975) {
        drops[i] = 0;
      }
      drops[i]++;
    }
  }

  resize();
  setInterval(draw, 50);
  window.addEventListener('resize', resize);
})();
