"""Fixed facts: the org, its repos, the project's fields and views, experiment status, estimates."""
ORG = "dorarobotics-dev"
REPOS = ("roadmap", "dora", "DORA_NAV", "dora-moveit2", "dora-studio", "octos", "dora-hub")
PROJECT_TITLE = "Embodied middleware v1.3"

ROW_NAMES = {
    "F": "F 基础 Foundation",
    "13": "13 感知类算子 Perception",
    "14": "14 控制类算子 Control",
    "15": "15 认知类算子 Cognition",
    "16": "16 数据处理类算子 Data processing",
    "17": "17 基础模型移植 Foundation models",
    "18": "18 云端适配对接 Cloud platform",
    "19": "19 核心驱动开发 Core drivers",
    "20": "20 边缘计算框架 Edge compute",
    "21": "21 安全适配 Security",
    "22": "22 仿真平台适配 Simulation",
    "23": "23 诊断工具适配 Diagnostics",
    "24": "24 SDK封装 SDK",
    "25": "25 采集系统 Motion capture",
}
STATUS_OPTIONS = ("Todo", "In progress", "In review", "Done (experiment)", "Done")
KIND_OPTIONS = ("requirement", "feature", "delivery")
BASIS_OPTIONS = ("new", "basis exists", "built, to move")

# project field name -> (data type, single-select options)
FIELDS = {
    "Row": ("SINGLE_SELECT", tuple(ROW_NAMES.values())),
    "Repo": ("SINGLE_SELECT", REPOS),
    "Kind": ("SINGLE_SELECT", KIND_OPTIONS),
    "Basis": ("SINGLE_SELECT", BASIS_OPTIONS),
    "Feature ID": ("TEXT", ()),
    "Estimate (days)": ("NUMBER", ()),
}

# view name, layout, filter ("" = none)
VIEWS = (
    [("Overview", "TABLE_LAYOUT", "")]
    + [(f"Row {row}", "BOARD_LAYOUT", f'row:"{name}"') for row, name in ROW_NAMES.items()]
    + [("By repo", "TABLE_LAYOUT", ""),
       ("Delivery", "TABLE_LAYOUT", "kind:delivery,requirement")]
)

LABELS = {
    **{f"row:{row}": ("0E8A16" if row == "F" else "1D76DB", name) for row, name in ROW_NAMES.items()},
    "status:new": ("D93F0B", "Feature map: nothing exists yet"),
    "status:basis-exists": ("FBCA04", "Feature map: code exists to wrap or fix"),
    "status:built-to-move": ("0E8A16", "Feature map: a working reference exists; the PR ports it"),
    "kind:requirement": ("5319E7", "A requirement group (workbook row)"),
    "kind:feature": ("C5DEF5", "One PR-sized feature"),
    "kind:delivery": ("BFD4F2", "A deliverable, not a PR to a code repo"),
}

# Contract-core experiment, from dora/docs/contract-core/feasibility.md ("What this slice delivered").
# ID -> (project Status, delivered, not delivered)
EXPERIMENT = {
    "F.01": ("In progress", "partly: the spec, deviations and this report are the material",
             "the proposal to dora maintainers is not written or sent"),
    "F.02": ("Done (experiment)", "fully, in the local copy: `dora_send_output_with_params`, C example",
             "not upstreamed; C input-side metadata read not added"),
    "F.03": ("In progress", "partly: frames declared per port (`input_frames`/`output_frames`, dataflow `frames:`)",
             "frame, rate and max-age in `dora-node.yml` itself"),
    "F.04": ("In progress",
             "partly: frame match, unknown and rejected frames, transform route, dynamic edges and pose wiring, "
             "the pose's parent frame when declared (check 4 in part, item 20), launch calibration and frame "
             "dictionary pinned, the first failing route per node reported; schema match is dora's existing type check",
             "declared validity handling; the pose's `child_frame`"),
    "F.06": ("In progress",
             "partly: degraded-forwarding tests and a 15-mutation sweep (every suite run per mutation) for the "
             "header, its Python binding, transform library, validator and frame-transform node",
             "a reusable kit for node authors"),
    "F.07": ("In progress", "partly: `robots/mickrobot-sim` (frames, extrinsics) in DORA_NAV",
             "the reference robots (agibot-d1-max, agibot-x2, aegis-ultra)"),
    "13.01": ("In progress", "fully for the Rust core and Python binding", "the C++ binding"),
    "13.02": ("Done (experiment)", "fully: `nodes/frame-transform`, static or pose-composed, run live", "none"),
    "13.17": ("Done (experiment)",
              "fully for the MuJoCo mobile base: every output (pointcloud, cloud, image, imu, Odometry, "
              "odom_pose, gnss) carries the header; `cloud` and `odom_pose` are typed",
              "typed image output"),
}
EXPERIMENT_EVIDENCE = (
    "Evidence: branch `exp/contract-core` in [dora](https://github.com/dorarobotics-dev/dora/tree/exp/contract-core) "
    "(26 commits on `1016eab0a`) and [DORA_NAV](https://github.com/dorarobotics-dev/DORA_NAV/tree/exp/contract-core) "
    "(14 commits on `a9257f5`); report "
    "[`docs/contract-core/feasibility.md`](https://github.com/dorarobotics-dev/dora/blob/exp/contract-core/docs/contract-core/feasibility.md). "
    "Rust 800 and Python 254 tests pass, `dora validate` 5/5, mutation sweep 15/15 caught, live run 579/579 clouds ok."
)

# Engineer-days from feasibility.md "Effort for later slices": only figures given for one ID.
ESTIMATES = {
    "13.01": 2, "13.03": 3, "13.04": 4, "13.06": 5, "13.08": 2, "13.09": 4, "13.10": 3, "13.12": 3,
    "13.13": 3, "13.14": 2, "13.16": 1,
    "F.05": 3, "24.01": 10, "24.03": 2, "21.01": 8, "F.08": 3, "F.09": 1, "F.10": 2, "24.02": 6,
    "24.05": 3, "24.06": 3,
    "16.01": 3, "16.02": 3, "16.03": 3, "16.04": 5, "16.05": 3,
    "19.03": 2, "14.13": 6, "19.01": 2, "14.15": 3, "14.11": 1, "14.03": 2, "14.06": 5, "14.07": 4,
    "14.14": 2,
}
REQ_ESTIMATES = {"13": 40, "16": 21}
# Figures the report gives for several IDs together, quoted in the requirement body.
ROW_ESTIMATE_NOTES = {
    "13": ["Row total 40 engineer-days (13.02 and 13.17 done in the experiment).",
           "13.05 / 19.07 time-align node: 5 days together.",
           "13.07, 13.11 RealSense/Orbbec and YOLO headers (dora-hub patches): 3 days together."],
    "14": ["Rows 14 and 19 together: 55 engineer-days (16 for headers alone).",
           "14.12 / 19.09 control and state schemas: 3 days together.",
           "14.01, 14.02 map save/load and relocalization: 4 days together.",
           "14.04, 14.05, 14.08 planner and controller wrapping: 3 days together.",
           "14.09 IK wrapping and 14.10 limit layer: 6 days together."],
    "16": ["Row total 21 engineer-days, including 2 for contract runtime helpers in Python and 2 for test "
           "mapping and the three data-processing mutations."],
    "19": ["Rows 14 and 19 together: 55 engineer-days (16 for headers alone).",
           "19.02, 19.05, 19.08 localization, arm integration, chassis configs: 6 days together.",
           "19.04 multi-waypoint missions and 19.06 arm task status: 6 days together.",
           "13.05 / 19.07 time-align node: 5 days together."],
    "21": ["Agent path (F.05, F.08–F.10, 21.01, 24.x): 41 engineer-days, plus 12–15 for security."],
    "24": ["Agent path (F.05, F.08–F.10, 21.01, 24.x): 41 engineer-days, plus 12–15 for security."],
}
