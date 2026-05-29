let launchParams = "";

export function setLaunchParams(raw) {
  launchParams = raw || "";
}

export async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-VK-Launch-Params": launchParams,
    ...(options.headers || {}),
  };
  const res = await fetch(path, { ...options, headers });
  const json = await res.json().catch(() => ({}));
  if (!res.ok || !json.ok) {
    throw new Error(json.error || `Ошибка ${res.status}`);
  }
  return json.data;
}

export const getMe = () => api("/api/me");
export const setUniversity = (university) =>
  api("/api/university", { method: "POST", body: JSON.stringify({ university }) });
export const setScheduleKind = (kind) =>
  api("/api/schedule-kind", { method: "POST", body: JSON.stringify({ kind }) });
export const getSchedule = ({ date, period = "today" } = {}) => {
  const q = new URLSearchParams();
  if (date) q.set("date", date);
  else q.set("period", period);
  return api(`/api/schedule?${q}`);
};
export const searchGroups = (q, limit = 80) =>
  api(`/api/groups/search?q=${encodeURIComponent(q)}&limit=${limit}`);
export const refreshGroups = () =>
  api("/api/groups/refresh", { method: "POST", body: "{}" });
export const refreshTeachers = () =>
  api("/api/teachers/refresh", { method: "POST", body: "{}" });
export const refreshAuditoriums = () =>
  api("/api/auditoriums/refresh", { method: "POST", body: "{}" });
export const searchTeachers = (q) =>
  api(`/api/teachers/search?q=${encodeURIComponent(q)}`);
export const searchAuditoriums = (q) =>
  api(`/api/auditoriums/search?q=${encodeURIComponent(q)}`);
export const bindGroup = (groupId, name) =>
  api("/api/profile/group", {
    method: "POST",
    body: JSON.stringify({ groupId, name }),
  });
export const bindTeacher = (teacherId, name) =>
  api("/api/profile/teacher", {
    method: "POST",
    body: JSON.stringify({ teacherId, name }),
  });
export const bindAud = (audId, name) =>
  api("/api/profile/aud", {
    method: "POST",
    body: JSON.stringify({ audId, name }),
  });
export const resetProfile = () =>
  api("/api/profile/reset", { method: "POST", body: "{}" });
export const eiosLogin = (login, password) =>
  api("/api/eios/login", {
    method: "POST",
    body: JSON.stringify({ login, password }),
  });
export const eiosLogout = () =>
  api("/api/eios/logout", { method: "POST", body: "{}" });
