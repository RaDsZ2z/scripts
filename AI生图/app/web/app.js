const state = {
  workspace: null,
  tasks: [],
  nextTaskId: 1,
  providers: [],
  activeJob: null,
  polling: null,
  writtenResults: new Set(),
  resultUrls: new Map(),
  completionShownFor: null,
};

const $ = (selector) => document.querySelector(selector);
const taskList = $("#taskList");

function toast(message, type = "") {
  const item = document.createElement("div");
  item.className = `toast ${type}`;
  item.textContent = message;
  $("#toastRegion").appendChild(item);
  window.setTimeout(() => item.remove(), 4200);
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function newTask(prompt = "", images = []) {
  return { id: state.nextTaskId++, prompt, images, error: "" };
}

function addTask(prompt = "", images = []) {
  state.tasks.push(newTask(prompt, images));
  renderTasks();
}

function tasksAreClear() {
  return state.tasks.length === 1
    && !state.tasks[0].prompt
    && state.tasks[0].images.length === 0;
}

function clearTasks() {
  if (tasksAreClear()) return;
  if (!window.confirm("确定要清除任务栏中的全部任务吗？")) return;
  state.tasks.forEach((task) => task.images.forEach((image) => URL.revokeObjectURL(image.url)));
  state.tasks = [newTask()];
  renderTasks();
  toast("任务已清除", "success");
}

function renderTasks() {
  taskList.replaceChildren();
  $("#clearTasks").disabled = tasksAreClear();
  state.tasks.forEach((task, index) => {
    const node = $("#taskTemplate").content.firstElementChild.cloneNode(true);
    node.dataset.taskId = task.id;
    node.classList.toggle("invalid", Boolean(task.error));
    node.querySelector(".task-number").textContent = `任务 ${String(index + 1).padStart(2, "0")}`;
    const input = node.querySelector(".prompt-input");
    input.value = task.prompt;
    node.querySelector(".char-count").textContent = `${task.prompt.length} 字`;
    node.querySelector(".validation-text").textContent = task.error;
    input.addEventListener("input", (event) => {
      task.prompt = event.target.value;
      task.error = "";
      node.classList.remove("invalid");
      node.querySelector(".validation-text").textContent = "";
      node.querySelector(".char-count").textContent = `${task.prompt.length} 字`;
    });
    node.querySelector(".duplicate-task").addEventListener("click", () => {
      const copy = newTask(task.prompt, task.images.map((image) => ({ ...image })));
      state.tasks.splice(index + 1, 0, copy);
      renderTasks();
    });
    node.querySelector(".delete-task").addEventListener("click", () => {
      if (state.tasks.length === 1) {
        task.prompt = "";
        task.images = [];
      } else {
        state.tasks.splice(index, 1);
      }
      renderTasks();
    });

    const dropzone = node.querySelector(".dropzone");
    dropzone.addEventListener("dragover", (event) => {
      event.preventDefault();
      dropzone.classList.add("dragging");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragging"));
    dropzone.addEventListener("drop", async (event) => {
      event.preventDefault();
      dropzone.classList.remove("dragging");
      await addDroppedImages(task, event.dataTransfer.items);
    });
    node.querySelector(".choose-images").addEventListener("click", () => chooseImages(task));

    const references = node.querySelector(".reference-list");
    task.images.forEach((image, imageIndex) => {
      const item = document.createElement("div");
      item.className = "reference-item";
      const thumbnail = document.createElement("img");
      thumbnail.src = image.url;
      thumbnail.alt = "";
      const copy = document.createElement("div");
      copy.className = "reference-copy";
      const name = document.createElement("strong");
      name.textContent = image.name;
      name.title = image.name;
      const path = document.createElement("span");
      path.textContent = image.relativePath;
      path.title = image.relativePath;
      copy.append(name, path);
      const remove = document.createElement("button");
      remove.className = "reference-remove";
      remove.type = "button";
      remove.textContent = "×";
      remove.title = "移除参考图";
      remove.addEventListener("click", () => {
        URL.revokeObjectURL(image.url);
        task.images.splice(imageIndex, 1);
        renderTasks();
      });
      item.append(thumbnail, copy, remove);
      references.appendChild(item);
    });
    taskList.appendChild(node);
  });
}

function clearSavedWorkspaceHandle() {
  if (!window.indexedDB) return Promise.resolve();
  return new Promise((resolve) => {
    const request = indexedDB.deleteDatabase("banana-workbench");
    request.onsuccess = resolve;
    request.onerror = resolve;
    request.onblocked = resolve;
  });
}

async function setWorkspace(handle, notify = true) {
  const permission = await handle.queryPermission({ mode: "readwrite" });
  if (permission !== "granted") {
    const requested = await handle.requestPermission({ mode: "readwrite" });
    if (requested !== "granted") throw new Error("未获得工作区读写权限");
  }
  state.workspace = handle;
  $("#workspaceName").textContent = handle.name;
  $("#workspaceName").title = handle.name;
  if (notify) toast(`工作区已切换为 ${handle.name}`, "success");
}

async function chooseWorkspace() {
  if (!window.showDirectoryPicker) {
    toast("当前浏览器不支持本地工作区，请使用最新版 Chrome 或 Edge", "error");
    return;
  }
  try {
    const handle = await window.showDirectoryPicker({ mode: "readwrite" });
    await setWorkspace(handle);
  } catch (error) {
    if (error.name !== "AbortError") toast(error.message, "error");
  }
}

async function referenceFromHandle(handle) {
  if (!state.workspace) throw new Error("请先选择工作区");
  const parts = await state.workspace.resolve(handle);
  if (!parts) throw new Error(`“${handle.name}”不在当前工作区内，请先复制到工作区`);
  const relativePath = parts.join("/");
  const file = await handle.getFile();
  if (!file.type.startsWith("image/")) throw new Error(`“${file.name}”不是支持的图片文件`);
  return {
    name: file.name,
    relativePath,
    handle,
    url: URL.createObjectURL(file),
    size: file.size,
  };
}

async function appendHandles(task, handles) {
  for (const handle of handles) {
    try {
      if (handle.kind !== "file") continue;
      const reference = await referenceFromHandle(handle);
      if (task.images.some((image) => image.name === reference.name)) {
        URL.revokeObjectURL(reference.url);
        throw new Error(`任务内已有同名文件“${reference.name}”`);
      }
      task.images.push(reference);
    } catch (error) {
      toast(error.message, "error");
    }
  }
  renderTasks();
}

async function addDroppedImages(task, items) {
  if (!state.workspace) {
    toast("请先选择工作区", "error");
    return;
  }
  if (!DataTransferItem.prototype.getAsFileSystemHandle) {
    toast("当前浏览器无法验证拖入路径，请使用最新版 Chrome 或 Edge", "error");
    return;
  }
  const handleRequests = Array.from(items)
    .filter((item) => item.kind === "file")
    .map((item) => item.getAsFileSystemHandle());
  const handles = await Promise.all(handleRequests);
  await appendHandles(task, handles.filter(Boolean));
}

async function chooseImages(task) {
  if (!state.workspace) {
    toast("请先选择工作区", "error");
    return;
  }
  try {
    const handles = await window.showOpenFilePicker({
      multiple: true,
      id: "banana-references",
      types: [{ description: "图片", accept: { "image/*": [".png", ".jpg", ".jpeg", ".webp", ".gif"] } }],
    });
    await appendHandles(task, handles);
  } catch (error) {
    if (error.name !== "AbortError") toast(error.message, "error");
  }
}

function normalizeRelativePath(path) {
  const normalized = String(path || "").trim().replaceAll("\\", "/").replace(/^\.\//, "");
  if (!normalized || normalized.startsWith("/") || /^[A-Za-z]:\//.test(normalized)) {
    throw new Error(`参考图路径必须是 workspace 相对路径：${path}`);
  }
  const parts = normalized.split("/").filter(Boolean);
  if (parts.includes("..")) throw new Error(`参考图路径不能包含 ..：${path}`);
  return parts;
}

async function fileHandleAtPath(path) {
  const parts = normalizeRelativePath(path);
  let directory = state.workspace;
  for (const part of parts.slice(0, -1)) directory = await directory.getDirectoryHandle(part);
  return directory.getFileHandle(parts.at(-1));
}

async function tasksFromData(data) {
  if (!state.workspace) throw new Error("请先选择工作区");
  if (!Array.isArray(data) || !data.length) throw new Error("任务文件必须是非空数组");
  const imported = [];
  const errors = [];
  for (let index = 0; index < data.length; index += 1) {
    const item = data[index] || {};
    const prompt = String(item.prompt || "");
    const rawPaths = item.image_path == null ? [] : (Array.isArray(item.image_path) ? item.image_path : [item.image_path]);
    const images = [];
    for (const rawPath of rawPaths) {
      try {
        const handle = await fileHandleAtPath(rawPath);
        const reference = await referenceFromHandle(handle);
        if (images.some((image) => image.name === reference.name)) {
          URL.revokeObjectURL(reference.url);
          throw new Error(`任务内存在同名参考图“${reference.name}”`);
        }
        images.push(reference);
      } catch (error) {
        errors.push(`任务 ${index + 1}：${error.message}`);
      }
    }
    imported.push(newTask(prompt, images));
  }
  if (errors.length) throw new Error(errors.slice(0, 4).join("；"));
  return imported;
}

async function importTaskData(data) {
  const imported = await tasksFromData(data);
  const hasContent = state.tasks.some((task) => task.prompt.trim() || task.images.length);
  if (hasContent && !window.confirm("导入会替换当前编辑区，是否继续？")) return;
  state.tasks.forEach((task) => task.images.forEach((image) => URL.revokeObjectURL(image.url)));
  state.tasks = imported;
  renderTasks();
  toast(`已导入 ${imported.length} 条任务`, "success");
}

async function fileToBase64(file) {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

async function writeFile(directory, name, content) {
  const handle = await directory.getFileHandle(name, { create: true });
  const writable = await handle.createWritable();
  await writable.write(content);
  await writable.close();
}

async function getDirectory(parent, name) {
  return parent.getDirectoryHandle(name, { create: true });
}

async function exportTasks() {
  if (!state.workspace) return toast("请先选择工作区", "error");
  try {
    await validateTasks(false);
    const payload = state.tasks.map((task) => ({
      prompt: task.prompt.trim(),
      image_path: task.images.map((image) => image.relativePath),
    }));
    await writeFile(state.workspace, "tasks_export.json", JSON.stringify(payload, null, 2));
    toast("已写入 workspace/tasks_export.json", "success");
  } catch (error) {
    toast(error.message, "error");
  }
}

async function validateTasks(markErrors = true) {
  if (!state.workspace) throw new Error("请先选择工作区");
  if (!state.tasks.length) throw new Error("至少需要一条任务");
  const errors = [];
  for (let index = 0; index < state.tasks.length; index += 1) {
    const task = state.tasks[index];
    task.error = "";
    if (!task.prompt.trim()) task.error = "请填写提示词";
    for (const image of task.images) {
      try {
        const resolved = await state.workspace.resolve(image.handle);
        if (!resolved || resolved.join("/") !== image.relativePath) throw new Error();
        const file = await image.handle.getFile();
        if (!file.size) throw new Error();
      } catch {
        task.error = `参考图已移动、删除或无法读取：${image.name}`;
        break;
      }
    }
    if (task.error) errors.push(`任务 ${index + 1}：${task.error}`);
  }
  if (markErrors) renderTasks();
  if (errors.length) throw new Error(errors[0]);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const body = await response.json();
  if (response.status === 401) {
    window.location.replace("/login");
    throw new Error("登录已失效");
  }
  if (!response.ok) throw new Error(body.error || `请求失败（${response.status}）`);
  return body;
}

function resetResultPreviews() {
  state.resultUrls.forEach((url) => URL.revokeObjectURL(url));
  state.resultUrls.clear();
  state.writtenResults.clear();
}

function resultKey(jobId, resultIndex) {
  return `${jobId}:${resultIndex}`;
}

async function submitBatch() {
  if (state.activeJob && ["queued", "running"].includes(state.activeJob.status)) {
    return toast("当前已有批次正在运行", "error");
  }
  try {
    await validateTasks();
    const provider = document.querySelector('input[name="provider"]:checked')?.value;
    if (!provider) throw new Error("请选择服务商");
    $("#submitBatch").disabled = true;
    $("#submitBatch").textContent = "正在读取参考图…";
    const tasks = [];
    for (const task of state.tasks) {
      const images = [];
      for (const reference of task.images) {
        const file = await reference.handle.getFile();
        images.push({
          name: reference.name,
          relative_path: reference.relativePath,
          mime: file.type || "image/png",
          data: await fileToBase64(file),
        });
      }
      tasks.push({ prompt: task.prompt.trim(), images });
    }
    const response = await api("/api/jobs", { method: "POST", body: JSON.stringify({ provider, tasks }) });
    state.activeJob = response.job;
    state.completionShownFor = null;
    resetResultPreviews();
    localStorage.setItem("banana-active-job", state.activeJob.id);
    renderJob();
    toast("批次已提交", "success");
    await syncJob();
    startPolling();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    $("#submitBatch").disabled = false;
    $("#submitBatch").textContent = "提交批次";
  }
}

function startPolling() {
  window.clearInterval(state.polling);
  state.polling = window.setInterval(syncJob, 1500);
}

async function syncJob() {
  const jobId = state.activeJob?.id;
  if (!jobId) return;
  try {
    const job = await api(`/api/jobs/${jobId}`);
    if (state.activeJob?.id !== jobId) return;
    state.activeJob = job;
    renderJob();
    if (state.workspace) await persistJobResults(job);
    if (state.activeJob?.id !== jobId) return;
    if (["completed", "stopped"].includes(job.status)) {
      window.clearInterval(state.polling);
      state.polling = null;
      $("#stopBatch").classList.add("hidden");
      $("#submitBatch").classList.remove("hidden");
      localStorage.removeItem("banana-active-job");
      notifyCompletionOnce(job);
    }
  } catch (error) {
    if (state.activeJob?.id !== jobId) return;
    window.clearInterval(state.polling);
    state.polling = null;
    toast(error.message, "error");
  }
}

function notifyCompletionOnce(job) {
  if (!job || state.completionShownFor === job.id) return;
  state.completionShownFor = job.id;
  const success = job.results.filter((result) => result.status === "success").length;
  const failed = job.results.filter((result) => result.status === "failed").length;
  const stopped = job.results.filter((result) => result.status === "stopped").length;
  const parts = [`成功 ${success} 张`];
  if (failed) parts.push(`失败 ${failed} 条`);
  if (stopped) parts.push(`停止 ${stopped} 条`);
  const title = job.status === "stopped" ? "批次已停止" : "批次处理完成";
  toast(`${title}：${parts.join("，")}`, failed || stopped ? "error" : "success");
}

function statusLabel(status) {
  return { idle: "空闲", queued: "等待", running: "生成中", success: "成功", failed: "失败", completed: "已完成", stopped: "已停止" }[status] || status;
}

function renderJob() {
  const job = state.activeJob;
  const running = job && ["queued", "running"].includes(job.status);
  $("#submitBatch").classList.toggle("hidden", Boolean(running));
  $("#stopBatch").classList.toggle("hidden", !running);
  $("#batchTitle").textContent = job ? `批次 ${job.folder}` : "暂无批次";
  const status = $("#batchStatus");
  status.className = `status-pill ${job?.status || "idle"}`;
  status.textContent = statusLabel(job?.status || "idle");
  const completed = job?.completed || 0;
  const total = job?.total || 0;
  $("#progressText").textContent = `${completed} / ${total}`;
  $("#progressBar").style.width = total ? `${completed / total * 100}%` : "0%";
  const list = $("#resultList");
  if (!job) {
    list.innerHTML = '<div class="empty-state">提交批次后，结果会显示在这里。</div>';
    return;
  }
  list.replaceChildren();
  job.results.forEach((result) => {
    const item = document.createElement("article");
    item.className = "result-item";
    const imageUrl = state.resultUrls.get(resultKey(job.id, result.index));
    if (imageUrl) {
      const image = document.createElement("img");
      image.className = "result-image";
      image.src = imageUrl;
      image.alt = `任务 ${result.index} 生成结果`;
      item.appendChild(image);
    } else {
      const placeholder = document.createElement("div");
      placeholder.className = "result-image placeholder";
      placeholder.textContent = result.status === "running" ? `第 ${result.attempt} 次请求` : statusLabel(result.status);
      item.appendChild(placeholder);
    }
    const row = document.createElement("div");
    row.className = "result-row";
    const copy = document.createElement("div");
    copy.className = "result-copy";
    const title = document.createElement("strong");
    title.textContent = `任务 ${String(result.index).padStart(2, "0")}`;
    const prompt = document.createElement("span");
    prompt.textContent = result.status === "failed" ? result.message : result.prompt;
    copy.append(title, prompt);
    const badge = document.createElement("span");
    badge.className = `status-pill ${result.status}`;
    badge.textContent = statusLabel(result.status);
    row.append(copy, badge);
    item.appendChild(row);
    list.appendChild(item);
  });
}

async function persistJobResults(job) {
  const output = await getDirectory(state.workspace, "output");
  const batch = await getDirectory(output, job.folder);
  const txt = await getDirectory(batch, "txt");
  for (const result of job.results) {
    const key = resultKey(job.id, result.index);
    if (result.status !== "success" || state.writtenResults.has(key)) continue;
    const response = await fetch(`/api/jobs/${job.id}/results/${result.index}/image`);
    if (!response.ok) continue;
    const blob = await response.blob();
    const extension = result.format === "jpg" ? "jpeg" : result.format;
    await writeFile(batch, `${result.index}.${extension}`, blob);
    await writeFile(txt, `${result.index}.txt`, result.text || "");
    state.writtenResults.add(key);
    if (state.activeJob?.id === job.id && !state.resultUrls.has(key)) {
      state.resultUrls.set(key, URL.createObjectURL(blob));
    }
  }
  const manifest = job.results.map((result) => {
    const success = result.status === "success";
    const extension = result.format === "jpg" ? "jpeg" : result.format;
    return {
      index: result.index,
      prompt: result.prompt,
      image_path: result.image_path.length === 0 ? null : result.image_path,
      success,
      message: result.message,
      output_file: success ? `output/${job.folder}/${result.index}.${extension}` : null,
    };
  });
  await writeFile(batch, "batch_results.json", JSON.stringify(manifest, null, 2));
  if (["completed", "stopped"].includes(job.status) && state.activeJob?.id === job.id) {
    const next = manifest.map((result) => ({
      prompt: "",
      image_path: result.output_file ? [result.output_file] : [],
    }));
    await writeFile(state.workspace, "tasks_next.json", JSON.stringify(next, null, 2));
  }
  if (state.activeJob?.id === job.id) renderJob();
}

async function stopBatch() {
  if (!state.activeJob) return;
  try {
    await api(`/api/jobs/${state.activeJob.id}/stop`, { method: "POST", body: "{}" });
    toast("停止请求已提交；当前正在请求的任务会完成本次尝试");
  } catch (error) {
    toast(error.message, "error");
  }
}

async function loadProviders() {
  const config = await api("/api/config");
  $("#logout").classList.toggle("hidden", !config.authentication_required);
  state.providers = config.providers;
  const list = $("#providerList");
  list.replaceChildren();
  config.providers.forEach((provider) => {
    const option = document.createElement("div");
    option.className = "provider-option";
    option.innerHTML = `
      <input type="radio" name="provider" id="provider-${provider.id}" value="${provider.id}" ${provider.id === "ikun" && provider.configured ? "checked" : ""} ${provider.configured ? "" : "disabled"}>
      <label for="provider-${provider.id}">
        <span class="provider-dot ${provider.configured ? "" : "offline"}"></span>
        <span class="provider-copy"><strong>${provider.label}</strong><span>${provider.configured ? provider.model : "未配置 API Key"}</span></span>
      </label>`;
    list.appendChild(option);
  });
  if (!document.querySelector('input[name="provider"]:checked')) {
    document.querySelector('input[name="provider"]:not(:disabled)')?.click();
  }
}

async function restoreState() {
  const jobId = localStorage.getItem("banana-active-job");
  if (jobId) {
    state.activeJob = { id: jobId };
    await syncJob();
    if (state.activeJob && ["queued", "running"].includes(state.activeJob.status)) startPolling();
  }
}

$("#chooseWorkspace").addEventListener("click", chooseWorkspace);
$("#addTask").addEventListener("click", () => addTask());
$("#clearTasks").addEventListener("click", clearTasks);
$("#exportTasks").addEventListener("click", exportTasks);
$("#submitBatch").addEventListener("click", submitBatch);
$("#stopBatch").addEventListener("click", stopBatch);
$("#logout").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  window.location.replace("/login");
});
$("#importJson").addEventListener("click", () => $("#jsonInput").click());
$("#importExcel").addEventListener("click", () => $("#excelInput").click());

$("#jsonInput").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  event.target.value = "";
  if (!file) return;
  try {
    await importTaskData(JSON.parse(await file.text()));
  } catch (error) {
    toast(`JSON 导入失败：${error.message}`, "error");
  }
});

$("#excelInput").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  event.target.value = "";
  if (!file) return;
  try {
    const data = await fileToBase64(file);
    const response = await api("/api/import-excel", { method: "POST", body: JSON.stringify({ data }) });
    await importTaskData(response.tasks);
  } catch (error) {
    toast(`Excel 导入失败：${error.message}`, "error");
  }
});

async function init() {
  await clearSavedWorkspaceHandle();
  addTask();
  try {
    await loadProviders();
    await restoreState();
  } catch (error) {
    toast(error.message, "error");
  }
  if (!window.showDirectoryPicker) toast("请使用最新版 Chrome 或 Edge 打开本工具", "error");
}

init();
