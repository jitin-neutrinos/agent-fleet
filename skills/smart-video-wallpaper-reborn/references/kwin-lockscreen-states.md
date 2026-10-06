# KWin lockscreen state machine and video wallpaper capture freeze

On Plasma 6 Wayland, the KWin lockscreen greeter covers the virtual output. When the screen locks, the capture freezes because the desktop output is hidden behind the greeter overlay. This is NOT a plasma-smart-video-wallpaper-reborn bug — it is a KWin compositor architecture constraint.

**Correct mechanism** — evdev grab of desk input. Do not rely on session lock (KWin greeter covers streamed virtual output; capture freezes on lock/wake). The plan reference is `~/Work/streamer/desk-lock-plan.md`.

**Symptoms** — video plays fine on the unlocked desktop, but when the screen locks (or the user switches to a VT), the video freezes or shows a still frame. This is expected: the KWin compositor redirects the wallpaper output to a different compositor loop during lockscreen, and if the wallpaper plugin does not have exclusive access to the head, the stream freezes.

**Workaround** — currently no software workaround within the plugin itself. The only correct path is the evdesk grab mechanism planned in the streamer desk lock plan. Until that is implemented, users should expect video to pause/still on lockscreen, and the audio may continue if the plugin routes it separately.

**Verification** — check `journalctl -f` while locking/unlocking; you may see `kwin_ql` or `qtquickcomp` state transitions. No video decoding usage change should occur during the lock transition — if it does, that indicates the plugin is still attempting to render on the primary output, which will fail under the greeter.

**Do not file a bug** for this behavior unless the video also crashes Plasma entirely (black screen + lockloop). The freeze is a compositor-level constraint, not a codec failure.