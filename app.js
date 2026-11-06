(function () {
  const $ = (id) => document.getElementById(id);
  const subjectsEl = $("subjects");
  const errorEl = $("error");
  const reportEl = $("report");
  const DEFAULT_SUBJECTS = ["Mathematics", "Science", "English", "Social Studies", "Computer Science"];

  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function addRow(name = "", marks = "", max = 100) {
    const row = document.createElement("div");
    row.className = "subject-row";
    row.innerHTML = `
      <input class="s-name" placeholder="Subject" aria-label="Subject name" value="${esc(name)}" />
      <input class="s-marks" type="number" min="0" step="any" placeholder="0" aria-label="Marks obtained" value="${esc(marks)}" />
      <input class="s-max" type="number" min="1" step="any" aria-label="Maximum marks" value="${esc(max)}" />
      <button type="button" class="remove" title="Remove subject" aria-label="Remove subject">×</button>`;
    row.querySelector(".remove").onclick = () => row.remove();
    subjectsEl.appendChild(row);
  }

  function resetRows() {
    subjectsEl.innerHTML = "";
    DEFAULT_SUBJECTS.forEach((n) => addRow(n));
  }

  function readSubjects() {
    return [...subjectsEl.querySelectorAll(".subject-row")].map((r) => ({
      name: r.querySelector(".s-name").value,
      marks: r.querySelector(".s-marks").value,
      max: r.querySelector(".s-max").value,
    }));
  }

  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.hidden = !msg;
  }

  function renderReport(student, res) {
    const rows = res.subjects
      .map(
        (s) => `<tr>
          <td>${esc(s.name)}</td><td>${s.marks}</td><td>${s.max}</td><td>${s.percentage}%</td>
          <td>${s.grade}</td>
          <td class="${s.passed ? "status-pass" : "status-fail"}">${s.passed ? "Pass" : "Fail"}</td></tr>`
      )
      .join("");
    const date = new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });

    reportEl.innerHTML = `
      <div class="report-title">
        <h2>REPORT CARD</h2>
        <span>${esc(student.exam || "Academic Report")}</span>
      </div>
      <div class="meta">
        <div><span>Name:</span> <strong>${esc(student.name)}</strong></div>
        <div><span>Roll / ID:</span> ${esc(student.roll || "—")}</div>
        <div><span>Class:</span> ${esc(student.cls || "—")}</div>
        <div><span>Date:</span> ${date}</div>
      </div>
      <table>
        <thead><tr><th>Subject</th><th>Marks</th><th>Max</th><th>%</th><th>Grade</th><th>Status</th></tr></thead>
        <tbody>${rows}</tbody>
        <tfoot><tr><td>Total</td><td>${res.total}</td><td>${res.maxTotal}</td><td>${res.percentage}%</td><td>${res.grade}</td><td></td></tr></tfoot>
      </table>
      <div class="summary">
        <div class="stat"><small>Total</small><b>${res.total} / ${res.maxTotal}</b></div>
        <div class="stat"><small>Percentage</small><b>${res.percentage}%</b></div>
        <div class="stat"><small>Grade</small><b>${res.grade}</b></div>
        <div class="stat result ${res.passed ? "pass" : "fail"}"><small>Result</small><b>${res.passed ? "PASS" : "FAIL"}</b></div>
      </div>
      <p class="remarks"><strong>Remarks:</strong> ${esc(res.remark)}${
        res.failedSubjects.length ? ` — Failed in: ${res.failedSubjects.map(esc).join(", ")}` : ""
      }</p>
      <div class="signatures"><div>Class Teacher</div><div>Parent / Guardian</div><div>Principal</div></div>
      <div class="report-actions no-print">
        <button type="button" class="primary" id="print">Print / Save as PDF</button>
      </div>`;
    reportEl.hidden = false;
    $("print").onclick = () => window.print();
    reportEl.scrollIntoView({ behavior: "smooth" });
  }

  $("form").addEventListener("submit", (e) => {
    e.preventDefault();
    showError("");
    const name = $("studentName").value.trim();
    if (!name) return showError("Please enter the student's name.");
    try {
      const result = Grading.computeResult(readSubjects());
      renderReport(
        { name, roll: $("rollNo").value.trim(), cls: $("className").value.trim(), exam: $("examName").value.trim() },
        result
      );
    } catch (err) {
      reportEl.hidden = true;
      showError(err.message);
    }
  });

  $("addSubject").onclick = () => addRow();
  $("reset").onclick = () => {
    $("form").reset();
    resetRows();
    showError("");
    reportEl.hidden = true;
  };
  $("sample").onclick = () => {
    $("studentName").value = "Aarav Sharma";
    $("rollNo").value = "2026-014";
    $("className").value = "10-B";
    $("examName").value = "Final Term 2026";
    subjectsEl.innerHTML = "";
    [88, 92, 79, 74, 95].forEach((m, i) => addRow(DEFAULT_SUBJECTS[i], m));
  };

  resetRows();
})();
