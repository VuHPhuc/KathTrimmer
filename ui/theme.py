# ui/theme.py — Color palette and design tokens for KathTrimmer

COLORS = {
    # Backgrounds
    "bg_main":       "#F4F6FB",
    "bg_card":       "#FFFFFF",
    "bg_sidebar":    "#EAEFF8",
    "bg_hover":      "#EEF2FF",
    "bg_drop":       "#F0F4FF",
    "bg_drop_hover": "#DDE6FF",

    # Accent (Indigo palette)
    "accent":        "#4F46E5",
    "accent_light":  "#818CF8",
    "accent_dark":   "#3730A3",
    "accent_bg":     "#EEF2FF",

    # Success / warning / danger
    "success":       "#10B981",
    "success_bg":    "#D1FAE5",
    "warning":       "#F59E0B",
    "danger":        "#EF4444",
    "danger_bg":     "#FEE2E2",

    # Text
    "text_primary":  "#111827",
    "text_secondary":"#6B7280",
    "text_muted":    "#9CA3AF",
    "text_on_accent":"#FFFFFF",

    # Borders
    "border":        "#E5E7EB",
    "border_focus":  "#4F46E5",

    # Slider
    "slider_track":  "#E5E7EB",
    "slider_fill":   "#4F46E5",
    "slider_handle": "#4F46E5",

    # Timeline
    "timeline_bg":   "#F3F4F6",
    "timeline_bar":  "#818CF8",
    "timeline_sel":  "#4F46E5",
    "in_marker":     "#10B981",
    "out_marker":    "#EF4444",
    "split_marker":  "#F59E0B",
}

FONTS = {
    "title":    ("Segoe UI", 20, "bold"),
    "heading":  ("Segoe UI", 14, "bold"),
    "subhead":  ("Segoe UI", 12, "bold"),
    "body":     ("Segoe UI", 11),
    "small":    ("Segoe UI", 9),
    "mono":     ("Consolas", 10),
    "label":    ("Segoe UI", 10),
    "btn":      ("Segoe UI", 11, "bold"),
}

RADIUS = {
    "card":   12,
    "btn":    8,
    "input":  6,
    "small":  4,
}

PADDING = {
    "card":   16,
    "section":10,
    "btn":    (10, 20),
}
