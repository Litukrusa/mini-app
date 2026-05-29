/** Настройки поиска как в VK-боте: ПИ ДГТУ и ДГТУ по-разному. */
export function universitySearchConfig(university) {
  if (university === "T") {
    return {
      showListOnOpen: true,
      minQueryLength: 0,
      groupPlaceholder: "Часть названия группы",
      teacherPlaceholder: "Фамилия или список преподавателей",
      audPlaceholder: "Номер или название аудитории",
      emptyTeacherHint: "Список пуст. Обновите кэш: python3 scripts/fetch_rasp_cache.py",
      emptyAudHint: "Список пуст. Обновите кэш: python3 scripts/fetch_rasp_cache.py",
      typeMoreHint: null,
    };
  }
  return {
    showListOnOpen: false,
    minQueryLength: 2,
    groupPlaceholder: "Часть названия группы (от 2 символов)",
    teacherPlaceholder: "Фамилия или часть ФИО (от 2 символов)",
    audPlaceholder: "Номер или название аудитории (от 2 символов)",
    emptyTeacherHint: null,
    emptyAudHint: null,
    typeMoreHint: "Введите минимум 2 символа для поиска (как в боте ДГТУ)",
  };
}
