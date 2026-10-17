// לקוח ה-API — מקביל לנתיבים ב-backend/app/api. כל המבנים מוגדרים ב-backend/app/contracts.py

// קוד הגישה למסכי הנציג והכללים — נשמר רק ללשונית הנוכחית (sessionStorage), לא לתמיד
const CODE_KEY = "access_code";

export function getAccessCode() {
  try {
    return sessionStorage.getItem(CODE_KEY);
  } catch {
    return null;
  }
}

export function setAccessCode(code) {
  try {
    if (code) sessionStorage.setItem(CODE_KEY, code);
    else sessionStorage.removeItem(CODE_KEY);
  } catch {
    /* מצב פרטי — יבקשו את הקוד שוב */
  }
}

async function request(path, options = {}) {
  const code = getAccessCode();
  const res = await fetch(`/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(code ? { "X-Access-Code": code } : {}), ...options.headers },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    // detail יכול להיות מחרוזת, או {message, problems} בשגיאת ולידציה של הכללים
    const err = new Error(typeof detail === "string" ? detail : detail?.message ?? `שגיאה ${res.status}`);
    err.problems = detail?.problems ?? [];
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export const api = {
  catalog: () => request("/catalog"),
  occupations: () => request("/occupations"),
  demoEmployees: () => request("/demo-employees"),
  compare: (profile, alternatives) => request("/compare", { method: "POST", body: { profile, alternatives } }),
  compareAll: (profile) => request("/compare/all", { method: "POST", body: { profile } }),
  demoCompare: (employeeId) => request(`/demo/compare/${employeeId}`),
  chat: (conversationId, message) =>
    request("/chat", { method: "POST", body: { conversation_id: conversationId, message } }),
  conversation: (id) => request(`/conversations/${id}`),
  explore: (id) => request(`/conversations/${id}/explore`, { method: "POST" }),
  correctProfile: (id, fields, currentParticipation) =>
    request(`/conversations/${id}/profile`, {
      method: "PATCH",
      body: { fields, current_participation: currentParticipation ?? null },
    }),
  loadDemo: (conversationId, employeeId) =>
    request(`/conversations/${conversationId ?? "new"}/demo/${employeeId}`, { method: "POST" }),
  checkAccess: (role, code) => request(`/auth/check/${role}`, { headers: { "X-Access-Code": code } }),
  repQuestions: (status) => request(`/rep/questions${status ? `?status=${status}` : ""}`),
  answerQuestion: (id, answer) => request(`/rep/questions/${id}/answer`, { method: "POST", body: answer }),
  searchVehicles: (q, year) =>
    request(`/vehicles/search?q=${encodeURIComponent(q)}${year ? `&year=${year}` : ""}`),
  rules: () => request("/rules"),
  previewRules: (rules) => request("/rules/preview", { method: "POST", body: { rules } }),
  saveRules: (rules) => request("/rules", { method: "PUT", body: { rules } }),
  undoRules: () => request("/rules/undo", { method: "POST" }),
};
