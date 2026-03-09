// Front LED Mount — RC Car Headlight Bracket
// Mounts to front shock tower plate via top bolt holes.
// Concave side cutouts clear the front shock absorbers.
// Single unified housing holds both LEDs with press-fit and flex clips.
//
// Print settings: 0.2mm layer height, 100% infill, no supports needed
// Material: PETG recommended (flex clips need some give)

/* ── Adjustable Parameters ── */

// LED module dimensions (3/4" dia, ~1" deep, tapers at back)
led_dia       = 19.05;  // 3/4 inch outer diameter
led_depth     = 25.4;   // ~1 inch total depth
led_taper_dia = 12;     // narrower diameter near wires at back
led_taper_len = 8;      // length of tapered section at back
wire_hole_dia = 6;      // wire exit hole diameter

// Press-fit tolerance
fit_tol       = 0.3;    // mm added to diameter for socket

// LED layout
led_spacing   = 30;     // center-to-center horizontal distance
led_y_offset  = -5;     // LEDs sit in lower-center area of plate

// Plate dimensions
plate_width   = 70;     // total width
plate_height  = 45;     // taller plate — holes at top, LEDs in middle
plate_thick   = 3;      // wall thickness

// Housing wall
housing_wall  = 2.5;
housing_r     = 3;      // rounding on housing block corners

// Mounting holes — at the TOP of the plate
mount_hole_dia     = 3.2;   // M3 bolt clearance
mount_hole_x       = 20;    // horizontal spread of top bolt holes
mount_hole_y       = 15;    // vertical offset upward from plate center

// Shock absorber clearance — concave cutouts on each side
shock_cutout_dia   = 28;    // diameter of circular cutout
shock_cutout_x     = 38;    // horizontal offset from center (on plate edge)
shock_cutout_y     = 0;     // vertical position of cutout center

// Flex clip parameters
clip_width    = 4;
clip_depth    = 1.0;
clip_slot_gap = 1.5;

// Cosmetic
corner_r      = 3;
visor_angle   = 10;     // forward tilt of LED housing

/* ── Derived Values ── */
socket_id     = led_dia + fit_tol;
socket_od     = socket_id + 2 * housing_wall;
socket_depth  = led_depth - led_taper_len;
half_spacing  = led_spacing / 2;

// Unified housing outer dimensions
housing_width  = led_spacing + socket_od;
housing_height = socket_od;

$fn = 64;

/* ── Modules ── */

// Rounded rectangle as 2D shape
module rounded_rect_2d(w, h, r) {
    offset(r = r)
        square([w - 2*r, h - 2*r], center = true);
}

// Plate outline with shock absorber clearance cutouts
module plate_profile() {
    difference() {
        rounded_rect_2d(plate_width, plate_height, corner_r);

        // Left shock absorber clearance curve
        translate([-shock_cutout_x, shock_cutout_y])
            circle(d = shock_cutout_dia);

        // Right shock absorber clearance curve
        translate([shock_cutout_x, shock_cutout_y])
            circle(d = shock_cutout_dia);
    }
}

// Flex clip relief slot for a single bore
module clip_slot(x_off, angle) {
    translate([x_off, 0, 0])
        rotate([0, 0, angle])
            translate([socket_id/2 + clip_depth/2, -clip_width/2, socket_depth * 0.25])
                cube([clip_slot_gap, clip_width, socket_depth * 0.5]);
}

// Flex clip bump inside a single bore
module clip_bump(x_off, angle) {
    translate([x_off, 0, 0])
        rotate([0, 0, angle])
            translate([socket_id/2 - clip_depth * 0.3, 0, socket_depth * 0.5])
                scale([1, 1, 2.5])
                    sphere(d = clip_depth * 1.6);
}

// Unified dual-LED housing — one solid block, two bores
module led_housing() {
    difference() {
        union() {
            // Main housing block — hull of two cylinders for smooth shape
            hull() {
                translate([-half_spacing, 0, 0])
                    cylinder(d = socket_od, h = socket_depth);
                translate([half_spacing, 0, 0])
                    cylinder(d = socket_od, h = socket_depth);
            }

            // Tapered back sections
            for (side = [-1, 1]) {
                translate([side * half_spacing, 0, -led_taper_len])
                    cylinder(d1 = led_taper_dia + fit_tol + 2 * housing_wall,
                             d2 = socket_od,
                             h = led_taper_len);
            }

            // Bridge between tapered sections at back
            hull() {
                for (side = [-1, 1]) {
                    translate([side * half_spacing, 0, -led_taper_len])
                        cylinder(d = led_taper_dia + fit_tol + 2 * housing_wall, h = 1);
                }
            }

            // Clip bumps — top and bottom of each bore
            for (side = [-1, 1]) {
                clip_bump(side * half_spacing, 90);
                clip_bump(side * half_spacing, 270);
            }
        }

        // Left LED bore
        translate([-half_spacing, 0, plate_thick])
            cylinder(d = socket_id, h = socket_depth);

        // Right LED bore
        translate([half_spacing, 0, plate_thick])
            cylinder(d = socket_id, h = socket_depth);

        // Left taper bore
        translate([-half_spacing, 0, -led_taper_len - 0.1])
            cylinder(d1 = led_taper_dia + fit_tol,
                     d2 = socket_id,
                     h = led_taper_len + 0.2);

        // Right taper bore
        translate([half_spacing, 0, -led_taper_len - 0.1])
            cylinder(d1 = led_taper_dia + fit_tol,
                     d2 = socket_id,
                     h = led_taper_len + 0.2);

        // Front openings for LED faces
        for (side = [-1, 1]) {
            translate([side * half_spacing, 0, -0.1])
                cylinder(d = socket_id, h = plate_thick + 0.2);
        }

        // Wire exits at back
        for (side = [-1, 1]) {
            translate([side * half_spacing, 0, -led_taper_len - 0.5])
                cylinder(d = wire_hole_dia, h = plate_thick + 1);
        }

        // Flex clip relief slots — top and bottom of each bore
        for (side = [-1, 1]) {
            clip_slot(side * half_spacing, 90);
            clip_slot(side * half_spacing, 270);
        }
    }
}

/* ── Main Assembly ── */

module front_led_mount() {
    difference() {
        union() {
            // Back plate with shock absorber cutouts
            linear_extrude(plate_thick)
                plate_profile();

            // Unified LED housing — projects forward from plate
            translate([0, led_y_offset, plate_thick])
                rotate([visor_angle, 0, 0])
                    translate([0, 0, -plate_thick])
                        led_housing();
        }

        // Top mounting holes
        for (side = [-1, 1]) {
            // Through-hole
            translate([side * mount_hole_x, mount_hole_y, -0.5])
                cylinder(d = mount_hole_dia, h = plate_thick + 1);

            // Countersink on front face
            translate([side * mount_hole_x, mount_hole_y, plate_thick - 1.2])
                cylinder(d = mount_hole_dia * 2, h = 2);
        }
    }
}

front_led_mount();
