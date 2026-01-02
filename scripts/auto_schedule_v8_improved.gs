/******************************************************
 * Auto Schedule – IMPROVED VERSION (v8)
 * 1. Only schedules VISIBLE (filtered) rows
 * 2. Better روز کاری/تعطیل handling
 * 3. Improved Jalali calendar integration
 * 4. Strict workday enforcement in scheduling
 *****************************************************/

/** ===== SETTINGS ===== */
const TEAM_SHEET_NAME = 'Team';
const TEAM_NAME_COLUMN = 'Name';
const TEAM_IMPL_SUM_COLUMN = 'Implementation SUM';

// Calendar sheet & labels
const CALENDAR_SHEET_NAME = 'calendar';
const CAL_STATUS_WORK_TEXT = 'روز کاری';
const CAL_STATUS_OFF_TEXT  = 'تعطیل';

// Active sheet column headers
const COL_ID = 'ردیف';
const COL_TASK_NAME = 'وظیفه';
const COL_CXV = 'CxV'; 
const COL_PRIORITY = 'اولویت';
const COL_NECESSITY = 'ضرورت';
const COL_STATUS = 'وضعیت';
const COL_ETA = 'ETA(h)';
const COL_TOTAL = 'Total (h)';
const COL_ASSIGNEES = 'افراد درگیر';
const COL_DEADLINE = 'ددلاین';
const COL_SPRINT = 'اسپرینت';
const COL_DEPENDS = 'وابستگی ها';
const COL_IMPL_START = 'تاریخ شروع پیاده سازی';

// Scheduling Logic
const FORCE_SAME_DAY_IF_START_SET = true;
const FORCE_SAME_DAY_IGNORE_CAPACITY = false;
const FORCE_SAME_DAY_MAX_TOTAL_HOURS = 12;

// Prioritization knobs
const PRIORITIZE_SINGLE_PERSON_TASKS = true;
const EXPLICIT_START_EARLIER_IS_BETTER = true;
const PERSON_HOURS_FROM_NAME_COLUMNS = true;
const JALALI_YEAR_FOR_SPRINTS = 1404;
const RESET_DEADLINE_CELL_STYLE_ON_EACH_RUN = true;

// Output controls
const OUTPUT_DEADLINE_AS_TEXT_ISO = false;
const OUTPUT_START_AS_TEXT_ISO    = false;
const APPLY_DEADLINE_DATE_FORMAT  = false;
const APPLY_START_DATE_FORMAT     = false;
const DEADLINE_DATE_FORMAT = 'yyyy-mm-dd';
const START_DATE_FORMAT    = 'yyyy-mm-dd';

/** ===== MENU ===== */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Auto Schedule')
    .addItem('Run (schedule all visible rows)', 'autoSchedule')
    .addToUi();
}

/** ===== MAIN ===== */
function autoSchedule() {
  ensureJalaali_();

  const ss = SpreadsheetApp.getActive();
  const sheet = ss.getActiveSheet();

  const data = sheet.getDataRange().getValues();
  if (data.length < 2) { 
    SpreadsheetApp.getUi().alert('هیچ داده‌ای برای زمان‌بندی یافت نشد.'); 
    return; 
  }

  // Get hidden rows info
  const hiddenRows = getHiddenRows_(sheet, data.length);
  
  const headers = data[0].map(String);
  const colIndex = (name) => headers.indexOf(name);
  const idx = {
    id: colIndex(COL_ID),
    name: colIndex(COL_TASK_NAME),
    cxv: colIndex(COL_CXV),
    nec: colIndex(COL_NECESSITY),
    pri: colIndex(COL_PRIORITY),
    st:  colIndex(COL_STATUS),
    eta: colIndex(COL_ETA),
    tot: colIndex(COL_TOTAL),
    asg: colIndex(COL_ASSIGNEES),
    ddl: colIndex(COL_DEADLINE),
    spr: colIndex(COL_SPRINT),
    dep: colIndex(COL_DEPENDS),
    start: colIndex(COL_IMPL_START)
  };
  
  ['id','spr','ddl','dep'].forEach(k => { 
    if (idx[k] === -1) throw new Error(`ستون الزامی یافت نشد: ${k}`); 
  });

  // ---- Department detection ----
  const norm = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9\u0600-\u06FF]/g,'');
  const taskDeptCols = {};
  headers.forEach((h, j) => {
    const n = norm(h);
    if (!n) return;
    const known = ['ai','backend','frontend','uiux','devops','support','monitoring','qa','mentorship','pm','research','documentation','meetings','po'];
    if (known.includes(n)) taskDeptCols[n] = j;
  });

  // ---- Load Data ----
  const team = loadTeamDeptCapacities_();
  const cal = buildCalendarIndex_(); 
  
  if (Object.keys(cal.jalaliMap).length === 0) {
    ss.toast("هشدار: ستون تاریخ شمسی در شیت calendar پیدا نشد. از محاسبات ریاضی استفاده می‌شود.", "Warning", 10);
  }

  const personColumns = {};
  if (PERSON_HOURS_FROM_NAME_COLUMNS) {
    team.names.forEach(name => {
      const j = headers.indexOf(name);
      if (j !== -1) personColumns[name] = j;
    });
  }

  // ---- Read tasks (ONLY VISIBLE ROWS) ----
  const tasks = [];
  let skippedHidden = 0;
  
  for (let r = 1; r < data.length; r++) {
    const row = data[r];
    
    // SKIP HIDDEN ROWS
    if (hiddenRows.has(r + 1)) { // +1 because sheet rows are 1-indexed
      skippedHidden++;
      continue;
    }
    
    // IGNORE COMPLETED
    const statusVal = String(row[idx.st] || '');
    if (statusVal.startsWith('۱۰') || statusVal.includes('تکمیل')) {
      continue; 
    }

    const id = row[idx.id];
    if (!id) continue;

    const sprintStr = String(row[idx.spr] || '');
    const sprintWindows = parseSprintRanges_(sprintStr, cal); 
    if (!sprintWindows.length) continue;

    // Dept hours
    const deptHours = {};
    let deptHoursSum = 0;
    Object.keys(taskDeptCols).forEach(nDept => {
      const j = taskDeptCols[nDept];
      const h = toNumber_(row[j]);
      if (h > 0) { deptHours[nDept] = h; deptHoursSum += h; }
    });

    let totalH = toNumber_(row[idx.tot]);
    const etaH  = toNumber_(row[idx.eta]);
    if (totalH <= 0 && etaH > 0) totalH = etaH;

    let perPersonHours = null;
    if (deptHoursSum <= 0 && Object.keys(personColumns).length) {
      const overrides = {};
      Object.keys(personColumns).forEach(name => {
        const v = toNumber_(row[personColumns[name]]);
        if (v > 0) overrides[name] = v;
      });
      if (Object.keys(overrides).length) {
        perPersonHours = overrides;
        totalH = Object.values(overrides).reduce((a,b)=>a+b,0);
      }
    }

    if (deptHoursSum <= 0 && totalH <= 0) continue;

    const assignees = parseAssignees_(String(row[idx.asg] || ''), team.caps);
    const dependsRaw = parseDependenciesRaw_(String(row[idx.dep] || '')); 
    const taskName = idx.name > -1 ? String(row[idx.name] || '').trim() : '';
    const startDate = parseFlexibleDate_(row[idx.start], cal);
    const cxvVal = (idx.cxv > -1) ? toNumber_(row[idx.cxv]) : 0;

    tasks.push({
      rIndex: r,
      id,
      name: taskName,
      nec: String(row[idx.nec] || ''),
      pri: String(row[idx.pri] || ''),
      cxv: cxvVal,
      status: statusVal,
      sprintWindows,
      startDate,
      dependsRaw,   
      depends: [],
      assignees,
      deptHours,
      totalH,
      perPersonHours
    });
  }

  if (skippedHidden > 0) {
    ss.toast(`${skippedHidden} ردیف مخفی شده نادیده گرفته شد.`, "Info", 5);
  }

  // ---- Resolve Dependencies ----
  const byId = {}; 
  const byName = {};
  tasks.forEach(t => {
    byId[String(t.id)] = t;
    if (t.name) {
       const cleanName = t.name.trim().toLowerCase().replace(/\s+/g, ' ');
       byName[cleanName] = t;
    }
  });
  tasks.forEach(t => {
    t.dependsRaw.forEach(depStr => {
      if (byId[depStr]) { t.depends.push(byId[depStr].id); return; }
      const cleanDep = String(depStr).trim().toLowerCase().replace(/\s+/g, ' ');
      if (byName[cleanDep]) { t.depends.push(byName[cleanDep].id); }
    });
  });

  // ---- Sort & Schedule ----
  const order = topoSort_(tasks, byId);
  const booked = {};
  team.names.forEach(n => booked[n] = {});

  // Priorities (CxV, Priority) - RESPECT topological order for dependencies
  const singlePerson = (t) => (t.assignees && t.assignees.length === 1);
  const explicitStartRank = (t) => (!EXPLICIT_START_EARLIER_IS_BETTER || !(t.startDate instanceof Date)) ? 99999999 : t.startDate.getTime();
  const cxvRank = (t) => (t.cxv > 0 ? (10000 - t.cxv) : 99999);
  
  // Assign dependency depth (how many dependencies deep is this task?)
  const depthMap = {};
  function getDepth(task) {
    if (depthMap[task.id] !== undefined) return depthMap[task.id];
    if (!task.depends || task.depends.length === 0) {
      depthMap[task.id] = 0;
      return 0;
    }
    let maxDepth = 0;
    task.depends.forEach(did => {
      const dep = byId[String(did)];
      if (dep) {
        const d = getDepth(dep);
        if (d >= maxDepth) maxDepth = d + 1;
      }
    });
    depthMap[task.id] = maxDepth;
    return maxDepth;
  }
  
  order.list.forEach(t => getDepth(t));

  const sortKey = (t) => {
    const a = depthMap[t.id] || 0;  // FIRST: Sort by dependency depth
    const b = cxvRank(t);
    const c = priorityRank_(t.pri);
    const d = (PRIORITIZE_SINGLE_PERSON_TASKS && singlePerson(t)) ? 0 : 1;
    const e = t.assignees ? t.assignees.length : 999;
    const f = explicitStartRank(t);
    const g = statusRank_(t.status);
    return [a,b,c,d,e,f,g].join('-');
  };
  order.list.sort((x,y)=> sortKey(x).localeCompare(sortKey(y)));

  const ddlUpdates = [];
  const startUpdates = [];
  const notes = [];
  const reds = [];

  order.list.forEach(task => {
    let est = tasksEarliestStart_(task, byId, task.sprintWindows, cal);

    let slices = [];
    if (Object.keys(task.deptHours).length > 0) {
      for (const nDept of Object.keys(task.deptHours)) {
        const hours = task.deptHours[nDept];
        let candidates = task.assignees.filter(a => getWeeklyDeptCap_(team, a, nDept) > 0);
        if (!candidates.length) candidates = task.assignees.slice();
        const perPerson = {};
        const share = hours / (candidates.length || 1);
        candidates.forEach(n => perPerson[n] = share);
        const res = allocateAcrossWindowsDept_({
          estCandidate: est, windows: task.sprintWindows, perPerson, normDept: nDept, team, booked, cal
        });
        slices.push({ dept: nDept, ...res });
      }
    } else {
      let perPerson = {};
      if (task.perPersonHours) {
        perPerson = Object.assign({}, task.perPersonHours);
      } else {
        const share = task.totalH / (task.assignees.length || 1);
        task.assignees.forEach(n => perPerson[n] = share);
      }
      const res = allocateAcrossWindowsDept_({
        estCandidate: est, windows: task.sprintWindows, perPerson, normDept: '__impl__', team, booked, cal
      });
      slices.push({ dept: '__impl__', ...res });
    }

    const valid = slices.filter(s => s.deadline);
    const startDay = valid.length ? new Date(Math.min.apply(null, valid.map(s => s.startDay.getTime()))) : null;
    
    // Strict Cap: Last window END date
    const lastWindowEnd = task.sprintWindows[task.sprintWindows.length - 1].end;
    
    let deadline = valid.length ? new Date(Math.max.apply(null, valid.map(s => s.deadline.getTime()))) : null;
    
    if (!deadline || deadline > lastWindowEnd) {
        deadline = lastWindowEnd;
    }

    task._deadline = deadline; 

    const overflow = slices.some(s => s.overflow);
    const note = slices.map(s => s.note).filter(Boolean).join(' | ');

    const ddlOut = OUTPUT_DEADLINE_AS_TEXT_ISO ? gDateToISO_(deadline) : deadline;
    ddlUpdates.push({ r: task.rIndex+1, c: idx.ddl+1, v: ddlOut });

    if (!task.startDate && startDay instanceof Date) {
      const startOut = OUTPUT_START_AS_TEXT_ISO ? gDateToISO_(startDay) : startDay;
      startUpdates.push({ r: task.rIndex+1, c: idx.start+1, v: startOut });
    }

    if (note) notes.push({ r: task.rIndex+1, c: idx.ddl+1, note });
    if (overflow) reds.push(task.rIndex+1);
  });

  // Apply updates in batches for performance
  if (RESET_DEADLINE_CELL_STYLE_ON_EACH_RUN && ddlUpdates.length) {
    const touched = Array.from(new Set(ddlUpdates.map(u => u.r)));
    const backgrounds = [];
    const fontColors = [];
    
    touched.forEach(r => {
      backgrounds.push([null]);
      fontColors.push([null]);
    });
    
    if (touched.length > 0) {
      const resetRange = sheet.getRange(touched[0], idx.ddl + 1, touched.length, 1);
      // Batch clear styles
      resetRange.setBackgrounds(backgrounds.map(() => [null]));
      resetRange.setFontColors(fontColors.map(() => [null]));
      resetRange.setFontStyles(fontColors.map(() => ['normal']));
    }
  }

  if (ddlUpdates.length) {
    const rng = sheet.getRange(2, idx.ddl + 1, data.length - 1, 1);
    const values = rng.getValues();
    ddlUpdates.forEach(u => { values[u.r - 2][0] = u.v; });
    rng.setValues(values);
    if (APPLY_DEADLINE_DATE_FORMAT) trySetNumberFormat_(rng, DEADLINE_DATE_FORMAT);
  }

  if (startUpdates.length) {
    const rngS = sheet.getRange(2, idx.start + 1, data.length - 1, 1);
    const valsS = rngS.getValues();
    startUpdates.forEach(u => { valsS[u.r - 2][0] = u.v; });
    rngS.setValues(valsS);
    if (APPLY_START_DATE_FORMAT) trySetNumberFormat_(rngS, START_DATE_FORMAT);
  }

  // Batch apply notes and red highlights
  if (notes.length > 0) {
    notes.forEach(n => {
      try {
        sheet.getRange(n.r, n.c).setNote(n.note);
      } catch (e) {
        Logger.log('Could not set note: ' + e);
      }
    });
  }
  
  if (reds.length > 0) {
    reds.forEach(r => {
      try {
        sheet.getRange(r, idx.ddl + 1)
          .setBackground('#ffd5d5')
          .setFontColor('#b71c1c')
          .setFontStyle('italic');
      } catch (e) {
        Logger.log('Could not set red highlight: ' + e);
      }
    });
  }

  SpreadsheetApp.getUi().alert(`زمان‌بندی انجام شد.\n${tasks.length} وظیفه برنامه‌ریزی شد${skippedHidden > 0 ? ` (${skippedHidden} ردیف مخفی نادیده گرفته شد)` : ''}.`);
}

/************* HIDDEN ROWS DETECTION *************/
function getHiddenRows_(sheet, numRows) {
  const hiddenRows = new Set();
  
  try {
    // Check if there's an active filter
    const filter = sheet.getFilter();
    
    if (filter) {
      // Filter exists - need to check which rows are visible
      // Strategy: Assume all rows are hidden, then mark visible ones
      const allRows = new Set();
      for (let i = 2; i <= numRows; i++) { // Start from 2 (skip header)
        allRows.add(i);
      }
      
      // Get the visible range by checking a sample cell in each row
      const dataRange = sheet.getDataRange();
      const firstCol = dataRange.getColumn();
      
      // Check each row - if we can't read it, it's likely hidden
      for (let i = 2; i <= numRows; i++) {
        try {
          // Try to check if row is hidden by filter
          if (sheet.isRowHiddenByFilter(i)) {
            hiddenRows.add(i);
          }
        } catch (e) {
          // If check fails, assume visible
        }
      }
    }
    
    // Also check for manually hidden rows
    for (let i = 2; i <= numRows; i++) {
      try {
        if (sheet.isRowHiddenByUser(i)) {
          hiddenRows.add(i);
        }
      } catch (e) {
        // Ignore errors
      }
    }
  } catch (e) {
    Logger.log('Warning: Could not detect hidden rows: ' + e);
  }
  
  return hiddenRows;
}

/************* CALENDAR *************/
function buildCalendarIndex_() {
  const ss = SpreadsheetApp.getActive();
  const sh = ss.getSheetByName(CALENDAR_SHEET_NAME);
  if (!sh) throw new Error(`Sheet "${CALENDAR_SHEET_NAME}" یافت نشد.`);
  const values = sh.getDataRange().getValues();
  if (values.length < 2) throw new Error('calendar خالی است.');

  const headers = values[0].map(String);
  const dateCol = detectGregorianDateColumn_(values);
  if (dateCol === -1) throw new Error('ستون تاریخ میلادی در calendar یافت نشد.');
  
  // Robust Jalali column detection (column F = index 5)
  const jalaliCol = 5; // Column F (0-indexed)
  const jalaliMap = {};

  const workMap = {};
  for (let i = 1; i < values.length; i++) {
    const g = parseGregorianLoose_(values[i][dateCol]);
    if (!g) continue;

    // Map Jalali string to Gregorian Date
    if (jalaliCol !== -1 && jalaliCol < values[i].length) {
      let jVal = String(values[i][jalaliCol] || '').trim();
      jVal = normalizePersianDigits_(jVal);
      const jm = jVal.match(/^(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})$/);
      if (jm) {
        const key = `${jm[1]}-${('0'+jm[2]).slice(-2)}-${('0'+jm[3]).slice(-2)}`;
        jalaliMap[key] = new Date(g);
      }
    }

    const key = dateKey_(g);
    let isWork = null;
    let hours = null;
    
    for (let j=0; j<values[i].length; j++){
      const h = (headers[j] || '').trim();
      const v = values[i][j];
      
      if (typeof v === 'string') {
        const s = v.trim();
        // Explicit work/off detection
        if (s === CAL_STATUS_WORK_TEXT) isWork = true;
        if (s === CAL_STATUS_OFF_TEXT)  isWork = false;
        if (/ساعت|hours?/i.test(h) && /^\s*\d+/.test(s)) {
          hours = Number(s.replace(/[^\d.]/g,'')) || hours;
        }
      } else if (typeof v === 'number') {
        if (/روز\s*کاری/i.test(h)) { 
          if (v === 1) isWork = true;
          if (v === 0) isWork = false; 
        }
        if (/ساعت|hours?/i.test(h)) { 
          hours = Number(v); 
        }
      }
    }
    
    // Default to workday if not specified
    if (isWork === null) {
      const dow = g.getDay();
      // Default: Friday (5) is off, others are work
      isWork = (dow !== 5);
    }
    
    workMap[key] = { 
      work: !!isWork, 
      hours: (hours != null && hours >= 0) ? Number(hours) : null 
    };
  }

  function isWorkday(d) { 
    const e = workMap[dateKey_(d)]; 
    if (e) return !!e.work;
    // Default fallback
    const dow = d.getDay();
    return dow !== 5; // Friday is off
  }
  
  function defaultDayHours(d) {
    if (!isWorkday(d)) return 0;
    const dow = d.getDay();
    if (dow === 5) return 0; // Friday
    if (dow === 4) return 6; // Thursday
    return 8; // Other days
  }
  
  function dayHours(d) {
    const e = workMap[dateKey_(d)];
    if (!e || !e.work) return 0;
    if (e.hours != null) return e.hours;
    return defaultDayHours(d);
  }
  
  function nextWorkdayOnOrAfter(d) {
    let x = new Date(d); 
    x.setHours(0,0,0,0);
    for (let i=0; i<120; i++) { 
      if (isWorkday(x)) return x; 
      x = addDays_(x, 1); 
    }
    return null;
  }
  
  function startOfIranWeek(d) {
    const day = d.getDay();
    const back = (day + 1) % 7;
    return addDays_(d, -back);
  }
  
  function weekHoursWeight(d) {
    const ws = startOfIranWeek(d);
    let sum = 0; 
    for (let i=0; i<7; i++) { 
      const dt = addDays_(ws, i); 
      sum += dayHours(dt); 
    }
    return sum;
  }
  
  return { 
    isWorkday, 
    nextWorkdayOnOrAfter, 
    startOfIranWeek, 
    weekHoursWeight, 
    dayHours, 
    jalaliMap 
  };
}

function detectGregorianDateColumn_(values) {
  const head = values[0];
  for (let j=0; j<head.length; j++){
    for (let i=1; i<Math.min(10, values.length); i++){
      if (parseGregorianLoose_(values[i][j])) return j;
    }
  }
  return -1;
}

function parseGregorianLoose_(cell) {
  if (cell instanceof Date) { 
    const d = new Date(cell); 
    d.setHours(0,0,0,0); 
    return d; 
  }
  if (cell == null) return null;
  const s = String(cell).trim();
  const m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (!m) return null;
  const y=+m[1], mo=+m[2], da=+m[3];
  if (y>=1900 && mo>=1 && mo<=12 && da>=1 && da<=31) { 
    const d=new Date(y, mo-1, da); 
    d.setHours(0,0,0,0); 
    return d; 
  }
  return null;
}

function normalizePersianDigits_(s) {
  const persianDigits = '۰۱۲۳۴۵۶۷۸۹';
  return s.replace(/[۰-۹]/g, d => String(persianDigits.indexOf(d)));
}

/************* TEAM *************/
function loadTeamDeptCapacities_() {
  const ss = SpreadsheetApp.getActive();
  const sh = ss.getSheetByName(TEAM_SHEET_NAME);
  if (!sh) throw new Error(`Sheet "${TEAM_SHEET_NAME}" یافت نشد.`);
  
  const values = sh.getDataRange().getValues();
  if (values.length < 2) return { names:[], depts:new Set(), caps:{}, implSum:{} };

  const headers = values[0].map(String);
  const iName = headers.indexOf(TEAM_NAME_COLUMN);
  const iImpl = headers.indexOf(TEAM_IMPL_SUM_COLUMN);
  if (iName === -1) throw new Error(`ستون "${TEAM_NAME_COLUMN}" در Team یافت نشد.`);

  const norm = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9\u0600-\u06FF]/g,'');
  const exclude = new Set([norm(TEAM_NAME_COLUMN), norm('Sum'), norm(TEAM_IMPL_SUM_COLUMN), norm('Total / week')]);
  const deptCols = [];
  headers.forEach((h, j) => {
    const n = norm(h);
    if (!n || exclude.has(n)) return;
    const known = new Set(['ai','backend','frontend','uiux','devops','support','monitoring','qa','mentorship','pm','research','documentation','meetings','po']);
    if (known.has(n)) deptCols.push({ normDept: n, j });
  });

  const names = [];
  const caps = {};
  const implSum = {};

  for (let i=1; i<values.length; i++){
    const row = values[i];
    const name = String(row[iName] || '').trim();
    if (!name) continue;
    names.push(name);
    const per = {};
    deptCols.forEach(({normDept, j}) => { 
      const v = toNumber_(row[j]); 
      if (v>0) per[normDept] = v; 
    });
    caps[name] = per;
    if (iImpl !== -1) implSum[name] = toNumber_(row[iImpl]);
  }
  return { names, caps, implSum };
}

function getWeeklyDeptCap_(team, person, normDept) {
  if (normDept === '__impl__') return team.implSum[person] || 0;
  
  const m = team.caps[person] || {};
  let cap = m[normDept] || 0;

  if (cap <= 0) {
    const totalImpl = team.implSum[person] || 0;
    if (totalImpl > 0) return totalImpl;
  }
  return cap;
}

/************* SCHEDULING *************/
function tasksEarliestStart_(task, byId, windows, cal) {
  let est = windows && windows.length ? new Date(windows[0].start) : null;
  if (task.startDate instanceof Date) {
    est = (!est || task.startDate > est) ? new Date(task.startDate) : est;
  }

  task.depends.forEach(did => {
    const dep = byId[String(did)];
    if (dep && dep._deadline instanceof Date) {
      const after = addDays_(dep._deadline, 1);
      est = !est ? after : (after > est ? after : est);
    }
  });

  if (est) {
    const w = cal.nextWorkdayOnOrAfter(est);
    if (w) est = w;
  }
  return est;
}

function allocateAcrossWindowsDept_({ estCandidate, windows, perPerson, normDept, team, booked, cal }) {
  const unknowns = [];
  Object.keys(perPerson).forEach(n => {
    if (getWeeklyDeptCap_(team, n, normDept) <= 0) unknowns.push(n);
  });

  // 1. Force Same Day
  if (FORCE_SAME_DAY_IF_START_SET && (estCandidate instanceof Date) && cal.isWorkday(estCandidate)) {
    const totalRem = Object.values(perPerson).reduce((a,b)=>a+b,0);
    if (totalRem <= FORCE_SAME_DAY_MAX_TOTAL_HOURS) {
      let feasible = true;
      if (!FORCE_SAME_DAY_IGNORE_CAPACITY) {
        let sumFree = 0;
        for (const name of Object.keys(perPerson)) {
          sumFree += getDailyDeptCap_(team, name, estCandidate, normDept, booked, cal);
        }
        feasible = (sumFree + 1e-6) >= totalRem;
      }
      if (feasible) {
        return bookOneDay_(estCandidate, perPerson, normDept, booked, unknowns);
      }
    }
  }

  // 2. Standard Scheduling with strict workday enforcement
  let firstDay = null;
  let finalDay = null;
  const remaining = Object.assign({}, perPerson);

  for (const w of windows) {
    let est = new Date(w.start);
    if (estCandidate instanceof Date && estCandidate > est) est = estCandidate;
    const estW = cal.nextWorkdayOnOrAfter(est);
    if (!estW || estW > w.end) { 
      estCandidate = null; 
      continue; 
    }

    let date = new Date(estW);
    while (date <= w.end) {
      // STRICT: Only schedule on workdays
      if (!cal.isWorkday(date)) { 
        date = addDays_(date, 1); 
        continue; 
      }
      
      const key = dateKey_(date);
      let anyWork = false;

      const dailyCapCheck = {};
      let totalRemCheck = 0;
      let totalCapCheck = 0;
      
      for (const name of Object.keys(remaining)) {
        if (remaining[name] > 0) {
           const cap = getDailyDeptCap_(team, name, date, normDept, booked, cal);
           dailyCapCheck[name] = cap;
           totalRemCheck += remaining[name];
           totalCapCheck += cap;
        }
      }
      
      // Attempt to fit work
      if (totalRemCheck > 0 && totalCapCheck >= totalRemCheck) {
         for (const name of Object.keys(remaining)) {
            const rem = remaining[name];
            if (rem > 0) {
              if (!booked[name][key]) booked[name][key] = {};
              booked[name][key][normDept] = (booked[name][key][normDept] || 0) + rem;
              remaining[name] = 0;
              anyWork = true;
            }
         }
      } else {
         for (const name of Object.keys(remaining)) {
           let rem = remaining[name];
           if (rem <= 0) continue;
           const free = getDailyDeptCap_(team, name, date, normDept, booked, cal);
           if (free <= 0) continue;
           const take = Math.min(rem, free);
           if (take > 0) {
             if (!booked[name][key]) booked[name][key] = {};
             booked[name][key][normDept] = (booked[name][key][normDept] || 0) + take;
             remaining[name] -= take;
             anyWork = true;
           }
         }
      }

      if (anyWork) {
        if (!firstDay) firstDay = new Date(date);
        finalDay = new Date(date);
      }
      
      const sumRem = Object.values(remaining).reduce((a,b)=>a+b,0);
      if (sumRem <= 1e-4) {
        const note = unknowns.length ? (`ظرفیت نامشخص (${deptLabel_(normDept)}): ` + unknowns.join(', ')) : '';
        return { 
          startDay: firstDay || estW, 
          deadline: endOfDay_(finalDay || estW), 
          overflow: false, 
          note 
        };
      }
      
      date = addDays_(date, 1);
    }
    estCandidate = null;
  }

  // OVERFLOW logic
  const left = Object.values(remaining).reduce((a,b)=>a+b,0);
  let note = '';
  let overflow = false;
  
  if (left > 1e-4) { 
    overflow = true; 
    note += `کمبود ظرفیت (${deptLabel_(normDept)}): ${left.toFixed(1)}h`; 
  }
  if (unknowns.length) { 
    if (note) note += ' | '; 
    note += `ظرفیت نامشخص (${deptLabel_(normDept)}): ` + unknowns.join(', '); 
  }

  // Return deadline as the END of the LAST window processed
  const lastWindowEnd = windows[windows.length-1].end;
  const deadline = endOfDay_(lastWindowEnd);
  
  return { 
    startDay: firstDay || windows[0].start, 
    deadline, 
    overflow, 
    note 
  };
}

function bookOneDay_(date, perPerson, normDept, booked, unknowns) {
  const key = dateKey_(date);
  for (const name of Object.keys(perPerson)) {
    const rem = perPerson[name];
    if (rem > 0) {
      if (!booked[name][key]) booked[name][key] = {};
      booked[name][key][normDept] = (booked[name][key][normDept] || 0) + rem;
    }
  }
  return { 
    startDay: new Date(date), 
    deadline: endOfDay_(date), 
    overflow: false,
    note: unknowns.length ? (`ظرفیت نامشخص (${deptLabel_(normDept)}): ` + unknowns.join(', ')) : '' 
  };
}

function deptLabel_(normDept) { 
  return normDept === '__impl__' ? 'Implementation' : normDept; 
}

function getDailyDeptCap_(team, name, date, normDept, booked, cal) {
  if (!cal.isWorkday(date)) return 0;
  const weekly = getWeeklyDeptCap_(team, name, normDept);
  if (weekly <= 0) return 0;
  
  // Count workdays in the week containing this date
  const weekStart = cal.startOfIranWeek(date);
  let workdaysInWeek = 0;
  for (let i = 0; i < 7; i++) {
    const d = addDays_(weekStart, i);
    if (cal.isWorkday(d)) workdaysInWeek++;
  }
  
  if (workdaysInWeek <= 0) return 0;
  const perDay = weekly / workdaysInWeek;
  
  const key = dateKey_(date);
  const usedMap = (booked[name] && booked[name][key]) ? booked[name][key] : {};
  const used = usedMap[normDept] || 0;
  return Math.max(0, perDay - used);
}

/************* HELPERS *************/
function ensureJalaali_() {
  if (typeof jalaali === 'undefined' || !jalaali.toGregorian) {
    throw new Error('کتابخانه‌ی جلالی یافت نشد.');
  }
}

function jalToGDate_(jy, jm, jd, endOfDay) {
  const g = jalaali.toGregorian(jy, jm, jd);
  const d = new Date(g.gy, g.gm - 1, g.gd);
  if (endOfDay) d.setHours(23,59,59,999); 
  else d.setHours(0,0,0,0);
  return d;
}

function jalToKey_(y, m, d) {
  return `${y}-${('0'+m).slice(-2)}-${('0'+d).slice(-2)}`;
}

function parseSprintRanges_(s, cal) {
  if (!s) return [];
  s = normalizePersianDigits_(s);
  const parts = String(s).split(/[,،]/).map(p=>p.trim()).filter(Boolean);
  const out = [];
  
  parts.forEach(p => {
    const m = p.match(/(\d{1,2})-(\d{1,2})\s*(?:to|تا)\s*(\d{1,2})-(\d{1,2})/i);
    if (!m) return;
    const jm1 = +m[1], jd1 = +m[2], jm2 = +m[3], jd2 = +m[4];
    
    const keyStart = jalToKey_(JALALI_YEAR_FOR_SPRINTS, jm1, jd1);
    const keyEnd   = jalToKey_(JALALI_YEAR_FOR_SPRINTS, jm2, jd2);

    let start, end;

    // Try calendar lookup first
    if (cal.jalaliMap && cal.jalaliMap[keyStart]) {
      start = new Date(cal.jalaliMap[keyStart]);
      start.setHours(0,0,0,0);
    } else {
      start = jalToGDate_(JALALI_YEAR_FOR_SPRINTS, jm1, jd1, false);
    }

    if (cal.jalaliMap && cal.jalaliMap[keyEnd]) {
      end = new Date(cal.jalaliMap[keyEnd]);
      end.setHours(23,59,59,999);
    } else {
      end = jalToGDate_(JALALI_YEAR_FOR_SPRINTS, jm2, jd2, true);
      if (end < start) end.setFullYear(end.getFullYear() + 1);
    }

    // Ensure end date is a workday - if not, move back to previous workday
    if (cal.nextWorkdayOnOrAfter) {
      let adjustedEnd = new Date(end);
      adjustedEnd.setHours(0,0,0,0);
      
      // Move backwards to find last workday
      for (let i = 0; i < 7; i++) {
        if (cal.isWorkday(adjustedEnd)) {
          end = new Date(adjustedEnd);
          end.setHours(23,59,59,999);
          break;
        }
        adjustedEnd = addDays_(adjustedEnd, -1);
      }
    }

    out.push({ start, end });
  });
  
  out.sort((a,b)=> a.start - b.start);
  return out;
}

function parseFlexibleDate_(cell, cal) {
  if (cell instanceof Date) { 
    const d = new Date(cell); 
    d.setHours(0,0,0,0); 
    return d; 
  }
  if (!cell) return null;
  
  let s = String(cell).trim();
  s = normalizePersianDigits_(s);
  const m = s.match(/^(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})$/);
  if (!m) return null;
  
  const y=+m[1], mo=+m[2], da=+m[3];
  
  // Check if it's Gregorian (year >= 1900)
  if (y >= 1900) { 
    const d = new Date(y, mo-1, da); 
    d.setHours(0,0,0,0); 
    return d; 
  }
  
  // Otherwise it's Jalali - try lookup first
  const key = jalToKey_(y, mo, da);
  if (cal && cal.jalaliMap && cal.jalaliMap[key]) {
    return new Date(cal.jalaliMap[key]);
  }
  
  // Fallback to calculation
  return jalToGDate_(y, mo, da, false);
}

function toNumber_(v) { 
  if (typeof v==='number') return v; 
  if(!v) return 0; 
  const n=Number(String(v).replace(/[^\d.\-]/g,'')); 
  return isFinite(n)?n:0; 
}

function parseAssignees_(s, teamMap){
  if (!s) return [];
  const names = String(s).split(/[,،؛|\/\-]+/).map(x=>x.trim()).filter(Boolean);
  const valid = names.filter(n => teamMap[n] != null || true);
  return valid.length ? valid : names;
}

function parseDependenciesRaw_(s){
  if (!s) return [];
  return String(s).split(/[,،]+/).map(t => t.trim()).filter(Boolean);
}

function topoSort_(tasks, byId){
  const indeg = {}; 
  tasks.forEach(t => indeg[String(t.id)] = 0);
  tasks.forEach(t => t.depends.forEach(d => { 
    if (byId[String(d)]) indeg[String(t.id)]++; 
  }));
  
  const q = []; 
  Object.keys(indeg).forEach(id => { 
    if (indeg[id] === 0) q.push(byId[id]); 
  });
  
  const out = [];
  while (q.length) { 
    const u = q.shift(); 
    out.push(u);
    tasks.forEach(v => { 
      if (v.depends.includes(u.id)) { 
        indeg[String(v.id)]--; 
        if (indeg[String(v.id)] === 0) q.push(v); 
      } 
    });
  }
  
  const cycle = out.length !== tasks.length;
  return { list: out, cycle };
}

function priorityRank_(s) { 
  const order=['Highest','High','Medium','Low']; 
  const i=order.indexOf(String(s)); 
  return i===-1?9:i; 
}

function statusRank_(s){
  const order = [
    '۶. در حال پیاده سازی',
    '۸. آماده تحویل',
    '۷. تست فنی',
    '۵.  آماده پیاده سازی فنی',
    '۴. در مرحله طراحی',
    '۳. آماده سازی یوزر استوری',
    '۶.۵ توقف پیاده سازی فنی'
  ];
  const i = order.findIndex(x => String(s).indexOf(x) !== -1); 
  return i===-1?9:i;
}

function dateKey_(d) { 
  return Utilities.formatDate(d, Session.getScriptTimeZone(), 'yyyy-MM-dd'); 
}

function addDays_(d, n) { 
  const x=new Date(d); 
  x.setDate(x.getDate()+n); 
  x.setHours(0,0,0,0); 
  return x; 
}

function endOfDay_(d) { 
  const x=new Date(d); 
  x.setHours(23,59,59,999); 
  return x; 
}

function gDateToISO_(d) { 
  return Utilities.formatDate(d, Session.getScriptTimeZone(), 'yyyy-MM-dd'); 
}

function trySetNumberFormat_(rng, fmt) { 
  try { 
    rng.setNumberFormat(fmt); 
  } catch(e) { 
    const msg=String(e); 
    if(!(msg.includes('typed column')||msg.toLowerCase().includes('number format'))) throw e; 
  } 
}
