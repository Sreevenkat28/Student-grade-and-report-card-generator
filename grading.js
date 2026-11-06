/* Grading logic — pure functions, no DOM. Works in browser and Node. */
(function (root) {
  const PASS_PERCENT = 40; // minimum % needed in each subject and overall

  const GRADE_SCALE = [
    { min: 90, grade: "A+", remark: "Outstanding" },
    { min: 80, grade: "A", remark: "Excellent" },
    { min: 70, grade: "B+", remark: "Very Good" },
    { min: 60, grade: "B", remark: "Good" },
    { min: 50, grade: "C", remark: "Satisfactory" },
    { min: 40, grade: "D", remark: "Needs Improvement" },
    { min: 0, grade: "F", remark: "Fail — Must Reappear" },
  ];

  function gradeFor(percentage) {
    return GRADE_SCALE.find((g) => percentage >= g.min);
  }

  const round2 = (n) => Math.round((n + Number.EPSILON) * 100) / 100;

  /** Validate one subject entry. Returns an error string or null. */
  function validateSubject(s) {
    if (!s.name || !String(s.name).trim()) return "Subject name is required.";
    const max = Number(s.max);
    if (s.max === "" || s.max == null || !Number.isFinite(max) || max <= 0)
      return `Maximum marks for "${s.name}" must be greater than 0.`;
    if (s.marks === "" || s.marks == null || !Number.isFinite(Number(s.marks)))
      return `Enter marks for "${s.name}".`;
    const marks = Number(s.marks);
    if (marks < 0) return `Marks for "${s.name}" cannot be negative.`;
    if (marks > max)
      return `Marks for "${s.name}" (${marks}) exceed the maximum (${max}).`;
    return null;
  }

  /**
   * subjects: [{ name, marks, max }]
   * Returns { total, maxTotal, percentage, grade, remark, passed, failedSubjects, subjects }
   */
  function computeResult(subjects) {
    if (!subjects.length) throw new Error("Add at least one subject.");
    for (const s of subjects) {
      const err = validateSubject(s);
      if (err) throw new Error(err);
    }

    const rows = subjects.map((s) => {
      const marks = Number(s.marks);
      const max = Number(s.max);
      const percentage = round2((marks / max) * 100);
      return {
        name: String(s.name).trim(),
        marks,
        max,
        percentage,
        grade: gradeFor(percentage).grade,
        passed: percentage >= PASS_PERCENT,
      };
    });

    const total = round2(rows.reduce((a, r) => a + r.marks, 0));
    const maxTotal = round2(rows.reduce((a, r) => a + r.max, 0));
    const percentage = round2((total / maxTotal) * 100);
    const failedSubjects = rows.filter((r) => !r.passed).map((r) => r.name);
    // Must clear the overall % AND every individual subject.
    const passed = percentage >= PASS_PERCENT && failedSubjects.length === 0;
    const overall = gradeFor(percentage);

    return {
      total,
      maxTotal,
      percentage,
      grade: overall.grade,
      remark: passed ? overall.remark : "Not promoted — must reappear in failed subject(s)",
      passed,
      failedSubjects,
      subjects: rows,
    };
  }

  const api = { PASS_PERCENT, GRADE_SCALE, gradeFor, validateSubject, computeResult };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Grading = api;
})(typeof window !== "undefined" ? window : globalThis);
