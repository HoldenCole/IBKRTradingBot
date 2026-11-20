"""Design tokens for the weekly report. One place for every color and size."""

# Quadrant colors — validated with the dataviz palette checker (all pairs, light surface):
# worst colour-blind separation dE 8.0, worst normal-vision separation dE 18.0.
Q = {1: "#3a6fc4", 2: "#17896b", 3: "#e09a00", 4: "#c9403c"}
Q_NAME = {1: "Recovering", 2: "Advancing", 3: "Rolling over", 4: "Declining"}
Q_DESC = {1: "below zero, rising", 2: "above zero, rising", 3: "above zero, falling", 4: "below zero, falling"}
Q_TEXT_ON = {1: "#ffffff", 2: "#ffffff", 3: "#11161c", 4: "#ffffff"}     # label colour inside each fill

INK = "#11161c"
INK2 = "#4b5661"
MUTED = "#87919b"
HAIR = "#dfe3e6"
GRID = "#eceff1"
PAPER = "#f6f5f1"
SURFACE = "#ffffff"
REF = "#a9b1b9"          # reference lines (moving averages, trend lines)
TIER_RAMP = {"CONS": "#9fb8cf", "MOD": "#6d93b5", "AGG": "#3d6d96", "VAGG": "#173f63"}

UNIT = {"D": "day", "W": "week", "M": "month"}
TF_NAME = {"D": "Daily", "W": "Weekly", "M": "Monthly"}
