/** Текущий объект расписания (группа / преподаватель / аудитория). */
export function getActiveSelection(me) {
  if (!me) return null;

  const kind = me.scheduleKind || "group";
  const fromKind = me.selections?.[kind];
  if (fromKind?.id != null) {
    return { ...fromKind, kind };
  }

  if (me.activeSelection?.id != null) {
    return { ...me.activeSelection, kind: me.scheduleKind || kind };
  }

  if (me.focus?.id != null) {
    return { ...me.focus, kind: me.focus.kind || kind };
  }

  for (const k of ["group", "teacher", "aud"]) {
    const s = me.selections?.[k];
    if (s?.id != null) {
      return { ...s, kind: k };
    }
  }

  return null;
}
