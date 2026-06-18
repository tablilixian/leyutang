(function () {
  'use strict';

  var sources = window.__AUDIO_SOURCES__;
  if (!sources || sources.length === 0) return;

  document.body.style.paddingBottom = '75px';

  var audio = new Audio();
  var currentIndex = 0;
  var isPlaying = false;
  var isLoading = false;
  var wasPlayingBeforeSeek = false;

  var bar = document.createElement('div');
  bar.id = 'audio-player-bar';
  bar.className = 'active';

  var inner = document.createElement('div');
  inner.className = 'ap-inner';

  var controls = document.createElement('div');
  controls.className = 'ap-controls';

  var playBtn = document.createElement('button');
  playBtn.className = 'ap-play-btn';
  playBtn.title = '\u64AD\u653E/\u6682\u505C';
  playBtn.textContent = '\u25B6';

  var info = document.createElement('div');
  info.className = 'ap-info';

  var sectionName = document.createElement('div');
  sectionName.className = 'ap-section-name';
  sectionName.textContent = sources[0].label;

  var progress = document.createElement('div');
  progress.className = 'ap-progress';

  var seek = document.createElement('input');
  seek.type = 'range';
  seek.className = 'ap-seek';
  seek.min = '0';
  seek.max = '100';
  seek.value = '0';
  seek.step = '0.1';

  var timeDisplay = document.createElement('span');
  timeDisplay.className = 'ap-time';
  timeDisplay.textContent = '00:00 / 00:00';

  var select = document.createElement('select');
  select.className = 'ap-section-select';
  for (var i = 0; i < sources.length; i++) {
    var opt = document.createElement('option');
    opt.value = i;
    opt.textContent = sources[i].label;
    select.appendChild(opt);
  }

  progress.appendChild(seek);
  progress.appendChild(timeDisplay);
  info.appendChild(sectionName);
  info.appendChild(progress);
  controls.appendChild(playBtn);
  controls.appendChild(info);
  controls.appendChild(select);
  inner.appendChild(controls);
  bar.appendChild(inner);
  document.body.appendChild(bar);

  function formatTime(t) {
    if (isNaN(t) || !isFinite(t)) return '00:00';
    var m = Math.floor(t / 60);
    var s = Math.floor(t % 60);
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  }

  function updateTime() {
    if (!audio.duration) return;
    var pct = (audio.currentTime / audio.duration) * 100;
    seek.value = pct;
    seek.style.background = 'linear-gradient(to right, var(--accent, #8b4513) 0%, var(--accent, #8b4513) ' + pct + '%, var(--border, #e0d5c8) ' + pct + '%, var(--border, #e0d5c8) 100%)';
    timeDisplay.textContent = formatTime(audio.currentTime) + ' / ' + formatTime(audio.duration);
  }

  function setLoading(loading) {
    isLoading = loading;
    if (loading) {
      playBtn.innerHTML = '<span class="ap-loading"></span>';
    } else {
      playBtn.innerHTML = '';
      playBtn.textContent = isPlaying ? '\u23F8' : '\u25B6';
    }
  }

  function loadSource(index) {
    if (index < 0 || index >= sources.length) return;
    setLoading(true);
    playBtn.className = 'ap-play-btn';
    isPlaying = false;
    currentIndex = index;
    sectionName.textContent = sources[index].label;
    select.value = index;
    audio.src = sources[index].src;
    audio.load();
  }

  function play() {
    if (isLoading) return;
    if (!audio.src) return;
    isPlaying = true;
    doPlay();
    var p = audio.play();
    if (p && typeof p.catch === 'function') {
      p.catch(function () {
        isPlaying = false;
        doPause();
      });
    }
  }

  function doPlay() {
    isPlaying = true;
    playBtn.textContent = '\u23F8';
    playBtn.className = 'ap-play-btn playing';
  }

  function doPause() {
    isPlaying = false;
    playBtn.textContent = '\u25B6';
    playBtn.className = 'ap-play-btn';
  }

  function togglePlay() {
    if (isLoading) return;
    if (isPlaying) {
      audio.pause();
      doPause();
    } else {
      play();
    }
  }

  // Seek while dragging (visual only, don't seek audio during drag)
  var isSeeking = false;
  seek.addEventListener('input', function () {
    if (!audio.duration) return;
    var pct = parseFloat(this.value);
    var t = (pct / 100) * audio.duration;
    timeDisplay.textContent = formatTime(t) + ' / ' + formatTime(audio.duration);
  });

  seek.addEventListener('mousedown', function () {
    if (audio.duration) {
      isSeeking = true;
      wasPlayingBeforeSeek = isPlaying;
      if (isPlaying) audio.pause();
    }
  });

  seek.addEventListener('touchstart', function () {
    if (audio.duration) {
      isSeeking = true;
      wasPlayingBeforeSeek = isPlaying;
      if (isPlaying) audio.pause();
    }
  });

  seek.addEventListener('change', function () {
    if (!audio.duration || !isSeeking) return;
    var pct = parseFloat(this.value);
    audio.currentTime = (pct / 100) * audio.duration;
    isSeeking = false;
    if (wasPlayingBeforeSeek) {
      play();
    }
  });

  select.addEventListener('change', function () {
    var idx = parseInt(this.value, 10);
    if (idx !== currentIndex) {
      loadSource(idx);
      play();
    }
  });

  playBtn.addEventListener('click', togglePlay);

  document.addEventListener('keydown', function (e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;
    if (e.code === 'Space') {
      e.preventDefault();
      togglePlay();
    }
  });

  audio.addEventListener('play', function () {
    isPlaying = true;
    doPlay();
  });

  audio.addEventListener('pause', function () {
    if (isPlaying) doPause();
  });

  audio.addEventListener('loadedmetadata', function () {
    setLoading(false);
    if (!isSeeking) updateTime();
  });

  audio.addEventListener('canplay', function () {
    setLoading(false);
  });

  audio.addEventListener('timeupdate', function () {
    if (!isSeeking) updateTime();
  });

  audio.addEventListener('ended', function () {
    if (currentIndex < sources.length - 1) {
      loadSource(currentIndex + 1);
      play();
    } else {
      isPlaying = false;
      doPause();
      seek.value = 0;
      seek.style.background = '';
      timeDisplay.textContent = '00:00 / 00:00';
      audio.currentTime = 0;
    }
  });

  audio.addEventListener('error', function () {
    setLoading(false);
    isPlaying = false;
    playBtn.className = 'ap-play-btn error';
    playBtn.textContent = '\u26A0';
    sectionName.textContent = sources[currentIndex].label + ' (\u52A0\u8F7D\u5931\u8D25)';
  });

  loadSource(0);

})();
