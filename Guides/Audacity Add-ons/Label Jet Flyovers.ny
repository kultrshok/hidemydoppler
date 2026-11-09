;nyquist plug-in
;version 4
;type analyze
;name "Label Jet Flyovers..."
;action "Scanning for aircraft flyovers..."
;info "Scrubgnome - marks spans where an aircraft flyover dominates.\nSelect the whole track (or a region) and run; adds one label per flyover.\nThis FLAGS flyovers so you know where to clean. It does not measure them."

;; A jet flyover has a telltale shape: a slow swell of low-frequency roar
;; (engine + broadband turbulence, mostly below ~500 Hz) that rises over a
;; few seconds, peaks overhead, then fades - while mid/high energy stays
;; comparatively flat. We follow the low-band vs high-band level over time
;; and label stretches where the low band leads for long enough to be a
;; flyover rather than a footstep, door slam or clipped word.

;control thresh "Flyover sensitivity: dB above baseline" real "" 4 0 20
;control mindur "Minimum flyover length (seconds)" real "" 2 1 15
;control split "Low/high split frequency (Hz)" int "" 500 150 2000

(setf *float-format* "%.3f")

;; ---- mono detection signal ----
(setf sig (if (arrayp *track*)
              (mult 0.5 (sum (aref *track* 0) (aref *track* 1)))
              *track*))
(setf sr (snd-srate sig))
(setf blk (max 1 (round (* 0.10 sr))))      ; 100 ms analysis block

;; ---- short-term RMS of each band (square -> block-average -> sqrt) ----
;; median of a Lisp array (baseline "normal" level for this clip)
(defun amedian (arr m)
  (let ((lst nil))
    (dotimes (i m) (push (aref arr i) lst))
    (setf lst (sort lst #'<))
    (nth (truncate (/ m 2)) lst)))

(defun band-rms (s)
  (snd-sqrt (snd-avg (mult s s) blk blk op-average)))

(setf lo (band-rms (lowpass8 sig split)))
(setf erate (snd-srate lo))                 ; = sr / blk
(setf dt (/ 1.0 erate))

;; ---- pull envelopes into Lisp arrays and decide there (robust) ----
(setf nlen (truncate (snd-length lo ny:all)))
(setf lov (snd-samples lo nlen))
(setf n (length lov))
(setf need (max 1 (round (/ mindur dt))))
(setf eps 1.0e-6)
(setf ref (+ (amedian lov n) eps))   ; typical low-band level for this clip

(setf labels nil)
(setf run 0)
(setf start 0)
(dotimes (i n)
  (setf d (* 20.0 (/ (log (/ (+ (aref lov i) eps) ref)) (log 10.0))))
  (cond ((>= d thresh)
         (if (= run 0) (setf start i))
         (setf run (1+ run)))
        (t
         (if (>= run need)
             (push (list (* start dt) (* i dt) "flyover") labels))
         (setf run 0))))
(if (>= run need)
    (push (list (* start dt) (* n dt) "flyover") labels))

(if labels (reverse labels)
    "No aircraft flyovers found above the threshold.")
