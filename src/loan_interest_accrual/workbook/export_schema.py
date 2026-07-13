RESULT_SHEET = "计提结果"
SEGMENT_SHEET = "分段明细"
COMPANY_SUMMARY_SHEET = "公司汇总"
CAPITALIZATION_SUMMARY_SHEET = "资本化汇总"
CHECK_SHEET = "校验结果"
PARAMETER_SHEET = "计算参数"

EXPORT_SHEET_NAMES = (
    RESULT_SHEET,
    SEGMENT_SHEET,
    COMPANY_SUMMARY_SHEET,
    CAPITALIZATION_SUMMARY_SHEET,
    CHECK_SHEET,
    PARAMETER_SHEET,
)

RESULT_HEADERS = (
    "计算月份",
    "贷款ID",
    "公司名称",
    "贷款合同号",
    "贷款银行",
    "是否资本化",
    "期初本金（元）",
    "当月放款合计（元）",
    "当月还本合计（元）",
    "月末本金（元）",
    "计息天数",
    "当月计提利息（元）",
    "资本化利息（元）",
    "费用化利息（元）",
)

SEGMENT_HEADERS = (
    "计算月份",
    "贷款ID",
    "分段序号",
    "分段开始日期",
    "分段结束日期",
    "分段天数",
    "计息本金（元）",
    "年利率",
    "计息基准",
    "未舍入分段利息（元）",
    "分段期末本金（元）",
    "分段触发说明",
)

COMPANY_SUMMARY_HEADERS = (
    "公司名称",
    "贷款笔数",
    "期初本金合计（元）",
    "当月放款合计（元）",
    "当月还本合计（元）",
    "月末本金合计（元）",
    "当月计提利息合计（元）",
    "资本化利息合计（元）",
    "费用化利息合计（元）",
)

CAPITALIZATION_SUMMARY_HEADERS = (
    "公司名称",
    "资本化贷款笔数",
    "资本化计息本金或月末本金汇总（元）",
    "资本化利息合计（元）",
)

CHECK_HEADERS = (
    "校验项",
    "状态",
    "期望值",
    "实际值",
)

PARAMETER_HEADERS = (
    "参数",
    "值",
)

PARAMETER_NAMES = (
    "计算月份",
    "期间开始日期",
    "期间结束日期",
    "金额单位",
    "利率输入格式",
    "放款生效规则",
    "还本生效规则",
    "贷款日期规则",
    "舍入规则",
    "应用版本",
    "生成时间",
)
