const form = document.querySelector("#calculation-form");
const monthInput = document.querySelector("#calculation-month");
const fileInput = document.querySelector("#workbook-file");
const calculateButton = document.querySelector("#calculate-button");
const exportButton = document.querySelector("#export-button");
const statusPanel = document.querySelector("#status-panel");
const statusTitle = document.querySelector("#status-title");
const statusMessage = document.querySelector("#status-message");
const errorSection = document.querySelector("#error-section");
const errorBody = document.querySelector("#error-body");
const errorCount = document.querySelector("#error-count");
const previewSection = document.querySelector("#preview-section");
const previewBody = document.querySelector("#preview-body");
const assetCount = document.querySelector("#asset-count");
const originalTotal = document.querySelector("#original-total");
const calculationPeriod = document.querySelector("#calculation-period");
const previewTotal = document.querySelector("#preview-total");
const validationStatus = document.querySelector("#validation-status");
const usageButton = document.querySelector("#usage-button");
const usageDialog = document.querySelector("#usage-dialog");
const dialogCloseButtons = usageDialog.querySelectorAll(
  ".dialog-close, .dialog-confirm",
);
const openDownloadsButton = document.querySelector("#open-downloads-button");
const exitToolButton = document.querySelector("#exit-tool-button");

function setBusy(busy, action) {
  calculateButton.disabled = busy;
  exportButton.disabled = busy || previewSection.hidden;
  if (busy) {
    statusPanel.hidden = false;
    statusPanel.className = "status-panel";
    statusTitle.textContent = action;
    statusMessage.textContent = "正在读取并校验文件，请稍候。";
  }
}

function showStatus(kind, title, message) {
  statusPanel.hidden = false;
  statusPanel.className = `status-panel ${kind}`;
  statusTitle.textContent = title;
  statusMessage.textContent = message;
}

function setDesktopBusy(busy, title, message) {
  calculateButton.disabled = busy;
  exportButton.disabled = busy || previewSection.hidden;
  openDownloadsButton.disabled = busy;
  exitToolButton.disabled = busy;
  document.body.setAttribute("aria-busy", String(busy));
  if (busy) {
    showStatus("", title, message);
  }
}

async function readDesktopActionResponse(response) {
  const payload = await response.json();
  if (typeof payload.message !== "string") {
    throw new Error("本地操作响应缺少明确说明。");
  }
  if (!response.ok || payload.success !== true) {
    throw new Error(payload.message);
  }
  return payload;
}

function wait(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

async function waitForDesktopShutdown(statusUrl) {
  const deadline = Date.now() + 12000;
  while (Date.now() < deadline) {
    let statusResponse;
    try {
      statusResponse = await fetch(statusUrl, {
        method: "GET",
        headers: {
          Accept: "application/json",
          "X-Local-Tool-Action": "loan-interest-accrual",
        },
        cache: "no-store",
      });
    } catch (statusError) {
      try {
        const healthResponse = await fetch("/health", {
          method: "GET",
          cache: "no-store",
        });
        if (!healthResponse.ok) {
          return;
        }
      } catch (healthError) {
        return;
      }
      await wait(250);
      continue;
    }

    const status = await readDesktopActionResponse(statusResponse);
    if (status.state !== "shutdown_pending") {
      throw new Error("安全退出状态无效，工具仍在运行。请重试。");
    }
    await wait(250);
  }

  throw new Error(
    "安全退出失败，工具仍在运行。请重试；如问题持续，请从开始菜单重新打开工具。",
  );
}

function buildFormData() {
  const data = new FormData();
  data.append("calculation_month", monthInput.value);
  if (fileInput.files.length > 0) {
    data.append("file", fileInput.files[0]);
  }
  return data;
}

function textCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value ?? "-";
  return cell;
}

function showErrors(errors) {
  previewSection.hidden = true;
  exportButton.disabled = true;
  errorBody.replaceChildren();

  for (const error of errors) {
    const row = document.createElement("tr");
    row.append(
      textCell(error.sheet),
      textCell(error.row),
      textCell(error.column_or_field),
      textCell(error.message),
      textCell(error.error_code),
    );
    errorBody.append(row);
  }

  errorCount.textContent = `${errors.length} 项错误`;
  errorSection.hidden = false;
}

function showPreview(payload) {
  errorSection.hidden = true;
  previewBody.replaceChildren();
  previewTotal.replaceChildren();

  for (const item of payload.preview) {
    const row = document.createElement("tr");
    row.append(
      textCell(item.sequence),
      textCell(item.primary_category),
      textCell(item.name),
      textCell(item.expense_category),
      textCell(item.original_value),
      textCell(item.residual_value),
      textCell(item.amortization_start),
      textCell(item.booking_month),
      textCell(item.amortization_term_months),
      textCell(item.monthly_amortization),
      textCell(item.cumulative_months),
      textCell(item.cumulative_amortization),
      textCell(item.current_required_amortization),
      textCell(item.current_actual_amortization),
      textCell(item.difference),
      textCell(item.ending_net_value),
    );
    if (item.fully_amortized) {
      row.classList.add("fully-amortized-row");
    }
    previewBody.append(row);
  }

  const total = document.createElement("tr");
  total.className = "total-row";
  total.append(
    textCell(""),
    textCell("合计"),
    textCell(""),
    textCell(""),
    textCell(payload.summary.original_value),
    textCell(""),
    textCell("/"),
    textCell("/"),
    textCell("/"),
    textCell(payload.summary.monthly_amortization),
    textCell("/"),
    textCell(payload.summary.cumulative_amortization),
    textCell(payload.summary.current_required_amortization),
    textCell(payload.summary.current_actual_amortization),
    textCell(""),
    textCell(payload.summary.ending_net_value),
  );
  previewTotal.append(total);

  assetCount.textContent = payload.summary.asset_count;
  originalTotal.textContent = payload.summary.original_value;
  calculationPeriod.textContent = payload.calculation_month;
  validationStatus.textContent = payload.validation_status;
  previewSection.hidden = false;
  exportButton.disabled = false;
}

async function parseJsonResponse(response) {
  try {
    return await response.json();
  } catch {
    return {
      success: false,
      errors: [{
        error_code: "RESPONSE_INVALID",
        sheet: null,
        row: null,
        column_or_field: "response",
        message: "服务返回了无法识别的响应。",
      }],
    };
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setBusy(true, "正在计算");

  try {
    const response = await fetch("/calculate", {
      method: "POST",
      body: buildFormData(),
    });
    const payload = await parseJsonResponse(response);
    if (!response.ok || !payload.success) {
      showErrors(payload.errors ?? []);
      showStatus("error", "校验未通过", "请根据错误清单修正文件后重新计算。");
      return;
    }
    showPreview(payload);
    showStatus("success", "计算完成", "预览已生成，可以核对后导出结果。");
  } catch {
    showErrors([{
      error_code: "REQUEST_FAILED",
      sheet: null,
      row: null,
      column_or_field: "request",
      message: "无法连接本地服务，请确认应用仍在运行。",
    }]);
    showStatus("error", "请求失败", "本地服务未响应。");
  } finally {
    setBusy(false, "");
  }
});

exportButton.addEventListener("click", async () => {
  setBusy(true, "正在导出");

  try {
    const response = await fetch("/export", {
      method: "POST",
      body: buildFormData(),
    });
    if (!response.ok) {
      const payload = await parseJsonResponse(response);
      showErrors(payload.errors ?? []);
      showStatus("error", "导出失败", "当前文件未通过校验，未生成结果文件。");
      return;
    }

    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") ?? "";
    const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    const filename = encodedName
      ? decodeURIComponent(encodedName[1])
      : "摊销结果.xlsx";
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);
    showStatus("success", "导出完成", "结果文件已保存到浏览器下载目录。");
  } catch {
    showStatus("error", "导出失败", "无法连接本地服务，请确认应用仍在运行。");
  } finally {
    setBusy(false, "");
  }
});

usageButton.addEventListener("click", () => {
  usageDialog.showModal();
});

for (const button of dialogCloseButtons) {
  button.addEventListener("click", () => {
    usageDialog.close();
  });
}

usageDialog.addEventListener("close", () => {
  usageButton.focus();
});

openDownloadsButton.addEventListener("click", async () => {
  setDesktopBusy(
    true,
    "正在打开下载目录",
    "正在请求 Windows 打开当前用户的下载目录。",
  );
  try {
    const response = await fetch("/desktop/open-downloads", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "X-Local-Tool-Action": "loan-interest-accrual",
      },
    });
    const payload = await readDesktopActionResponse(response);
    showStatus("success", "操作成功", payload.message);
  } catch (error) {
    showStatus("error", "操作失败", error.message);
  } finally {
    setDesktopBusy(false, "", "");
  }
});

exitToolButton.addEventListener("click", async () => {
  const confirmed = window.confirm(
    "退出后当前页面将无法继续使用，确认退出工具？",
  );
  if (!confirmed) {
    return;
  }

  let shutdownRequested = false;
  setDesktopBusy(
    true,
    "正在提交退出请求",
    "正在请求工具安全结束本机服务。",
  );
  try {
    const response = await fetch("/desktop/exit", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "X-Local-Tool-Action": "loan-interest-accrual",
      },
    });
    const payload = await readDesktopActionResponse(response);
    if (typeof payload.status_url !== "string") {
      throw new Error("退出响应缺少状态确认地址，工具仍在运行。请重试。");
    }
    showStatus("", "正在安全退出", payload.message);
    await waitForDesktopShutdown(payload.status_url);
    shutdownRequested = true;
    showStatus("success", "工具已安全退出", "本机服务已停止，可以关闭此页面。");
    return;
  } catch (error) {
    showStatus("error", "操作失败", error.message);
  } finally {
    if (!shutdownRequested) {
      setDesktopBusy(false, "", "");
    }
  }
});

fileInput.addEventListener("change", () => {
  previewSection.hidden = true;
  errorSection.hidden = true;
  exportButton.disabled = true;
});

monthInput.addEventListener("change", () => {
  previewSection.hidden = true;
  errorSection.hidden = true;
  exportButton.disabled = true;
});
