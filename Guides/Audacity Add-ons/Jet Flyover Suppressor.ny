;nyquist plug-in
;version 4
;type process
;name "Jet Flyover Suppressor..."
;action "Ducking aircraft flyovers..."
;info "hidemydoppler - detects aircraft flyovers and ducks them.\nSame detector as 'Label Jet Flyovers'; here it lowers the level during a\nflyover instead of labelling it. Start gentle and listen - it is a broadband\nduck, so it dims everything while the jet passes. For the full privacy pass\n(strip faint tones + metadata) use the hidemydoppler app."

;control reduce "Reduction during flyover (dB)" real "" 12 0 36
;control thresh "Flyover sensitivity: dB above baseline" real "" 4 0 20
;control split "Low/high split frequency (Hz)" int "" 500 150 2000
;control ramp "Fade in/out (seconds)" real "" 0.5 0.05 3

;; ---- mono detection signal (so stereo ducks together) ----
(setf sig (if (arrayp *track*)
              (mult 0.5 (sum (aref *track* 0) (aref *track* 1)))
              *track*))
(setf sr (snd-srate sig))
(setf blk (max 1 (round (* 0.10 sr))))          ; 100 ms analysis block

;; median of a Lisp array (baseline "normal" level for this clip)
(defun amedian (arr m)
  (let ((lst nil))
    (dotimes (i m) (push (aref arr i) lst))
    (setf lst (sort lst #'<))
    (nth (truncate (/ m 2)) lst)))

(defun band-rms (s)
  (snd-sqrt (snd-avg (mult s s) blk blk op-average)))

(setf lo (band-rms (lowpass8 sig split)))
(setf erate (snd-srate lo))                     ; block rate = sr / blk
(setf dt (/ 1.0 erate))

(setf nlen (truncate (snd-length lo ny:all)))
(setf lov (snd-samples lo nlen))
(setf n (length lov))
(setf eps 1.0e-6)
(setf ref (+ (amedian lov n) eps))   ; typical low-band level for this clip
(setf floorg (expt 10.0 (/ (- 0.0 reduce) 20.0)))   ; linear gain on a flyover

;; ---- per-block target gain: floorg inside a flyover, else 1.0 ----
(setf target (make-array n))
(dotimes (i n)
  (setf d (* 20.0 (/ (log (/ (+ (aref lov i) eps) ref)) (log 10.0))))
  (setf (aref target i) (if (>= d thresh) floorg 1.0)))

;; ---- slew-rate-limit it into smooth linear ramps (no click, no startup dip).
;;      step per block = full swing / ramp-length, applied both directions. ----
(setf steps (max 1 (round (/ ramp dt))))
(setf step (/ (- 1.0 floorg) steps))
(setf g (make-array n))
(setf prev 1.0)
(dotimes (i n)
  (let ((tg (aref target i)))
    (cond ((> tg prev) (setf prev (min tg (+ prev step))))
          ((< tg prev) (setf prev (max tg (- prev step))))
          (t (setf prev tg)))
    (setf (aref g i) prev)))

;; ---- gain array -> sound at block rate -> track rate, then apply ----
(setf gain-lo (snd-from-array 0.0 erate g))
(setf gain (force-srate sr gain-lo))            ; linear-interpolate up to sr
(mult *track* gain)
