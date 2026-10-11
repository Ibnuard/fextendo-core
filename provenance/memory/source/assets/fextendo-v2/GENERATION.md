# FEXTendo generated assets

Created with the built-in imagegen tool on 2026-09-28. Original PNGs are
retained here; the asset builder only crops transparent padding, fits them
to the target buffers and preserves alpha. All animation is rendered in C.

- `stadium.png`: inherited generated stadium/football-player backdrop from
  the interrupted redesign. Original source asset preserved.
- `gamepad-flat.png`: final flat gamepad; replaces the rejected detailed
  controller. Used at the top left.
- `wordmark.png`: rounded **FEXTendo**, used in the top-right branding.

## Gamepad final edit prompt

Clean up this exact flat gamepad icon for production. Keep its silhouette,
D-pad and four buttons. Remove the entire luminous white halo outside the
shape: all pixels outside the controller must be fully transparent, with
only narrow edge antialiasing. The icon body must be a single perfectly
uniform solid white fill. Buttons must be a single perfectly uniform dark
navy fill. No gradients anywhere, no shading, absolutely no glow or drop
shadow. Pure flat two-color pictogram only. Keep transparent background.
Use the exact simple geometry in this reference, no new details, no analog
sticks, no outline.

Reference was the previously generated flat version. The exported alpha
makes the area outside the controller transparent even when its RGB preview
shows a halo on black.

## Wordmark prompt

Create a single clean production wordmark logo reading exactly "FEXTendo".
Exact case: F E X T uppercase, e n d o lowercase. Only this word, no icon
and no other text. Wide horizontal composition on a genuinely transparent
background. Custom rounded geometric sans-serif lettering, softened
terminals and corners, precise consistent medium-bold weight, generous
readable shapes, polished and restrained console software branding. Pearl
white letters with a very subtle cool silver-to-white vertical gradient,
no visible outline or stroke, no neon rim, no bevel, no heavy 3D, no glow,
no shadow. All characters share one cohesive visual style and a straight
baseline. Strong legibility when the entire wordmark is about 150 pixels
wide in a dark navy launcher header. The word fills most of the canvas
width with small clear padding. Output just one final transparent wordmark asset.
