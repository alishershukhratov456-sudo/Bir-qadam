// =============================================================================
// DAILY QUOTES  (30 quotes; shown once per session via modal, then cycles)
// =============================================================================
const QUOTES = [
  { text: "Har bir yangi kun — yangi imkoniyat.", author: "Noma\u02bclum" },
  { text: "Kichik qadamlar ulug\u02bc yo\u02bclllarni yaratadi.", author: "Lao Tzu" },
  { text: "O\u02bczingga ishon — bu muvaffaqiyatning yarmi.", author: "Theodore Roosevelt" },
  { text: "Bugun qilgan narsang ertangi hayotingni belgilaydi.", author: "Noma\u02bclum" },
  { text: "Qiyinchilik — o\u02bcssishning boshqa nomi.", author: "Noma\u02bclum" },
  { text: "Maqsading bo\u02bclmasa, har qanday yo\u02bcl manzilga olib boradi.", author: "Lewis Carroll" },
  { text: "Eng katta yutuq — har kuni bir oz yaxshiroq bo\u02bclish.", author: "Noma\u02bclum" },
  { text: "Harakat qilmasdan hech narsa o\u02bczgarmaydi.", author: "Noma\u02bclum" },
  { text: "Yaxshi odat — kelajakga qilingan investitsiya.", author: "Noma\u02bclum" },
  { text: "Sen o\u02bcylayotganingdan kuchliroqsan.", author: "A.A. Milne" },
  { text: "Orzular — harakat bilan amalga oshadi, uyqu bilan emas.", author: "Noma\u02bclum" },
  { text: "Bir kun o\u02bctkazib yuborsang — ikki kun o\u02bctkazib yuborma.", author: "James Clear" },
  { text: "Eng muhim qadam — birinchi qadam.", author: "Noma\u02bclum" },
  { text: "O\u02bczingni taqqosla — kechagi o\u02bczingga, boshqalarga emas.", author: "Jordan Peterson" },
  { text: "Intizom — eng yaxshi do\u02bcsting.", author: "Noma\u02bclum" },
  { text: "Yaxshilik qilish ham odatga aylanishi mumkin.", author: "Noma\u02bclum" },
  { text: "Har kuni biroz o\u02bcqigan odam — yil oxirida boshqa dunyo ko\u02bcradi.", author: "Noma\u02bclum" },
  { text: "Qo\u02bcrquv — o\u02bcssishning belgisi. Shundan qo\u02bcrqma.", author: "Noma\u02bclum" },
  { text: "Hech narsa tugamaydi — faqat yangi bosqich boshlanadi.", author: "Noma\u02bclum" },
  { text: "Kech boshlagan ham g\u02bcalib bo\u02bclishi mumkin.", author: "Noma\u02bclum" },
  { text: "Mehnat hech qachon aldamaydi.", author: "Noma\u02bclum" },
  { text: "O\u02bczingga bergan so\u02bczing — eng muhim va\u02bcda.", author: "Noma\u02bclum" },
  { text: "Muvaffaqiyat — sekin-asta to\u02bcplangan kichik g\u02bcalabalar.", author: "Noma\u02bclum" },
  { text: "Bugun o\u02bczimdanman, ertaga ham o\u02bczimdanman.", author: "Noma\u02bclum" },
  { text: "Boshlamasdan hech narsa yaratilmaydi.", author: "Noma\u02bclum" },
  { text: "Hayot — ishlab chiqarish, nafaqat kutish.", author: "Noma\u02bclum" },
  { text: "Rivojlanish — jarayon, natija emas.", author: "Noma\u02bclum" },
  { text: "Eng zo\u02bcr sarmoya — o\u02bczingga qilgan sarmoya.", author: "Benjamin Franklin" },
  { text: "Sabr va izchillik — har qanday to\u02bcssiqni yengadi.", author: "Noma\u02bclum" },
  { text: "Bugun qilgan kichik harakating — ertangi katta o\u02bczgarishing.", author: "Noma\u02bclum" }
];

function getDailyQuote() {
  var key = 'yv_quote_idx';
  var idx = sessionStorage.getItem(key);
  if (idx === null) {
    idx = Math.floor(Math.random() * QUOTES.length);
    sessionStorage.setItem(key, idx);
  }
  return QUOTES[Number(idx) % QUOTES.length];
}

function showQuoteModal() {
  var modal = document.getElementById('quote-modal');
  var textEl = document.getElementById('qm-text');
  var authorEl = document.getElementById('qm-author');
  if (!modal) return;
  if (sessionStorage.getItem('yv_quote_shown')) {
    modal.remove();
    return;
  }
  var q = getDailyQuote();
  textEl.textContent = '\u201c' + q.text + '\u201d';
  authorEl.textContent = '— ' + q.author;
  var sideQuote = document.getElementById('daily-quote');
  if (sideQuote) sideQuote.textContent = q.text;
  requestAnimationFrame(function() {
    requestAnimationFrame(function() { modal.classList.add('open'); });
  });
  document.getElementById('qm-close').addEventListener('click', function() {
    modal.classList.remove('open');
    sessionStorage.setItem('yv_quote_shown', '1');
    setTimeout(function() { if (modal.parentNode) modal.remove(); }, 400);
  });
  modal.addEventListener('click', function(e) {
    if (e.target === modal) {
      var btn = document.getElementById('qm-close');
      if (btn) btn.click();
    }
  });
}

// =============================================================================
// DAY IMAGES  — seeded shuffle so each photo is randomly (but consistently)
// assigned to a specific day, no repeats until the 7-photo pool is exhausted,
// then the next shuffled round begins.
// =============================================================================
var TOTAL_PHOTOS = 7;

// Simple seeded LCG so the shuffle is deterministic for this user/session
// but looks random (not photo1→photo2→…).
function seededShuffle(arr, seed) {
  var a = arr.slice();
  var s = seed;
  for (var i = a.length - 1; i > 0; i--) {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    var j = Math.abs(s) % (i + 1);
    var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
  }
  return a;
}

// Build a mapping of day → photo index (1-based) for all 30 days.
// Uses a fixed seed (42) so the assignment is the same on every page load.
var DAY_PHOTO_MAP = (function() {
  var map = [];
  var seed = 42;
  for (var round = 0; round < Math.ceil(30 / TOTAL_PHOTOS); round++) {
    var pool = [];
    for (var p = 1; p <= TOTAL_PHOTOS; p++) pool.push(p);
    // Use a different seed each round so successive rounds differ
    var shuffled = seededShuffle(pool, seed + round * 997);
    for (var k = 0; k < shuffled.length; k++) map.push(shuffled[k]);
  }
  return map; // map[0] = photo for day 1, map[1] = photo for day 2, …
})();

function getPhotoForDay(day) {
  var idx = DAY_PHOTO_MAP[(day - 1) % DAY_PHOTO_MAP.length];
  return '/static/photo' + idx + '.png';
}

function updateDayImage(day) {
  var label = document.getElementById('day-image-label');
  var img   = document.getElementById('tip-day-image');
  if (!img) return;
  img.src = getPhotoForDay(day);
  img.alt = day + '-kun rasmi';
  if (label) label.textContent = 'KUN ' + String(day).padStart(2, '0') + ' / 30';
}

// =============================================================================
// DAY LOCKING — day N is accessible only if day N-1 is completed (day 1 always open)
// =============================================================================
function isDayLocked(n) {
  if (n <= 1) return false;
  return !(entries[n - 1] && entries[n - 1].completed);
}

// =============================================================================
// JOURNAL DATA
// =============================================================================
var days = [
  {title:"Men kimman?",task:"O'zing haqida 5 ta qisqa jumla yoz. Har birini Men... bilan boshlagin.",fields:[["about1","Men..."],["about2","Men..."],["about3","Men..."],["about4","Men..."],["about5","Men..."]],reflection:"Bugun men o'zimda nimani yaxshi ko'rdim?",quote:"O'zingni anglash — o'zgarishning birinchi qadami."},
  {title:"Mening kuchli tomonlarim",task:"O'zingdagi 3 ta kuchli tomonni yoz va har biriga misol keltir.",fields:[["strength1","Kuchli tomonim 1"],["example1","Misol"],["strength2","Kuchli tomonim 2"],["example2","Misol"],["strength3","Kuchli tomonim 3"],["example3","Misol"]],reflection:"Mening eng kuchli tomonim nima va uni qanday ishlatishim mumkin?",quote:"Kuchli tomonlaringni bilish — ulardan foydalanishning boshlanishi."},
  {title:"Mening maqsadlarim",task:"Keyingi 3 oy uchun 3 ta maqsad belgilagin.",fields:[["goal1","O'qish yoki bilim maqsadi"],["goal2","Shaxsiy rivojlanish maqsadi"],["goal3","Yaxshi odatlar maqsadi"]],reflection:"Ushbu maqsadlar nima uchun men uchun muhim?",quote:"Maqsad yo'nalish beradi, kichik qadamlar esa oldinga olib boradi."},
  {title:"Vaqtimni qadrlayman",task:"Bugun vaqtingni qanday ishlatganingni yoz. Eng muhim 3 ishni qayd et.",fields:[["task1","1-ish va sarflangan daqiqa"],["task2","2-ish va sarflangan daqiqa"],["task3","3-ish va sarflangan daqiqa"]],reflection:"Agar bugun 1 soat qo'shimcha vaqtim bo'lsa, uni nima uchun ishlatardim?",quote:"Vaqting — qayta tiklab bo'lmaydigan qimmatli boylik."},
  {title:"Yaxshi odat yarataman",task:"Bitta yangi yaxshi odat tanla va uni qanday boshlashingni yoz.",fields:[["habit","Yangi odat"],["habitWhy","Nima uchun muhim?"],["habitStart","Bugun qanday boshlayman?"]],reflection:"Yaxshi odatlar hayotimni qanday o'zgartirishi mumkin?",quote:"Kichik odatlar vaqt o'tib katta o'zgarishlar yaratadi."},
  {title:"Kitob va bilim",task:"10-15 daqiqa kitob o'qi yoki yangi biror narsani o'rgan.",fields:[["learning","Bugun o'qigan yoki o'rgangan narsam"],["interesting","Eng qiziqarli qismi"],["newThing","Yangi o'rgangan bitta narsam"]],reflection:"Bilim olish meni qanday o'zgartiryapti?",quote:"Har bir yangi bilim — yangi imkoniyat."},
  {title:"O'zimga ishonch",task:"O'zingga ishonch beruvchi 5 ta jumla yoz va ularni ovoz chiqarib o'qi.",fields:[["affirm1","Men..."],["affirm2","Men..."],["affirm3","Men..."],["affirm4","Men..."],["affirm5","Men..."]],reflection:"Men o'zimga qanday ishonch bera olaman?",quote:"O'zingga aytadigan gaplaring mehrli va dalda beruvchi bo'lsin."},
  {title:"Telefon va ekran vaqtini boshqarish",task:"Bugun telefondan foydalanish vaqtini 30 daqiqaga kamaytirishga harakat qil.",fields:[["screenToday","Bugun telefondan qancha foydalandim?"],["screenBefore","Oldingi o'rtacha vaqtim"],["screenInstead","Telefon o'rniga nima qildim?"]],reflection:"Telefondan kamroq foydalanish meni qanday his qildiradi?",quote:"Vaqtingni o'zing tanlagan narsalarga sarfla."},
  {title:"Sog'lom kun tartibi",task:"Bugungi kun tartibingni tekshir va kichik odatlarni belgilab chiq.",fields:[["wake","Erta uyg'ondim? (Ha/Yo'q va vaqt)"],["breakfast","Sog'lom nonushta qildim? (Ha/Yo'q)"],["movement","Harakat qildim? (Ha/Yo'q, nima?)"],["sleep","Erta uxladim? (Ha/Yo'q va vaqt)"]],reflection:"Sog'lom kun tartibi meni qanday his qildiradi?",quote:"O'zingga g'amxo'rlik qilish ham rivojlanishning bir qismi."},
  {title:"Oilamga mehr",task:"Oila a'zolaringdan biriga minnatdorchilik bildir yoki u bilan 15 daqiqa sifatli vaqt o'tkaz.",fields:[["familyWho","Kim bilan vaqt o'tkazdim?"],["familyWhat","Nima qildim?"]],reflection:"Oilam bilan sifatli vaqt o'tkazish menga qanday his berdi?",quote:"Mehr ko'pincha oddiy, samimiy harakatlarda ko'rinadi."},
  {title:"Oilamga yordam",task:"Bugun oilangdagi bir kishiga ataylab yordam ber yoki uni xursand qil.",fields:[["familyHelp","Oilam uchun qilgan yaxshi ishim"]],reflection:"Men oilamga mehrimni qanday ko'rsataman?",quote:"Mehr kichik ishlardan boshlanadi."},
  {title:"Yaxshi do'st qanday bo'ladi?",task:"Sinfdoshingga samimiy yordam ber yoki yaxshi gap ayt. Yaxshi do'stning 3 xususiyatini yoz.",fields:[["friendAct","Bugun qilgan yaxshi ishim"],["friend1","Yaxshi do'stning 1-xususiyati"],["friend2","2-xususiyati"],["friend3","3-xususiyati"]],reflection:"Men qanday do'st bo'lishni xohlayman?",quote:"Yaxshi do'st bo'lish — yaxshi inson bo'lishning bir qismi."},
  {title:"Telefonni men boshqaraman",task:"Telefon ishlatish vaqtini kamida 30 daqiqaga kamaytirishga harakat qil.",fields:[["screenNow","Bugun telefondan foydalanish vaqtim"],["screenAverage","Oldingi o'rtacha vaqtim"]],reflection:"Telefonimga kamroq vaqt sarflasam, bu vaqtni nimaga sarflashim mumkin?",quote:"Vaqtingni o'zing boshqar — odatlaring seni boshqarmasin."},
  {title:"Kitob bilan uchrashuv",task:"Bugun kamida 15 daqiqa kitob o'qi.",fields:[["bookName","Kitob nomi"],["pages","O'qigan sahifalarim"],["bookPart","Menga yoqqan joy"],["bookIdea","Kitob bergan bitta fikr"]],reflection:"Nega ba'zi kitoblar insonni o'zgartirishi mumkin?",quote:"Har bir o'qilgan sahifa — yangi fikr."},
  {title:"Mening kuchli tomonim",task:"O'zingdagi kamida 5 ta yaxshi sifatni yoz.",fields:[["quality1","1-sifat"],["quality2","2-sifat"],["quality3","3-sifat"],["quality4","4-sifat"],["quality5","5-sifat"],["feedback","Ishonchli inson aytgan kuchli tomonim"]],reflection:"Qaysi kuchli tomonimdan kelajakda ko'proq foydalanishim mumkin?",quote:"O'z kuchingni bilish — o'ziga ishonchning boshlanishi."},
  {title:"Mening kelajakdagi kasbim",task:"Qiziqishing mumkin bo'lgan 3 ta kasbni va ularga kerakli bilimlarni yoz.",fields:[["career1","1-kasb: nima uchun yoqadi va qanday bilim kerak?"],["career2","2-kasb: nima uchun yoqadi va qanday bilim kerak?"],["career3","3-kasb: nima uchun yoqadi va qanday bilim kerak?"]],reflection:"Bugungi o'qishim kelajakdagi hayotim bilan qanday bog'liq?",quote:"Kelajak bir kunda qurilmaydi — bugungi kichik qadamlardan boshlanadi."},
  {title:"Xatolarim — dushmanim emas",task:"Yaqinda qilgan bitta xatongni esla va undan o'rgangan narsangni yoz.",fields:[["mistake","Men qilgan xato"],["lesson","Bundan nimani o'rgandim?"],["nextTime","Keyingi safar men..."]],reflection:"Xato qilishdan qo'rqmaslik menga qanday yordam beradi?",quote:"Xato — yakun emas. Xato — o'rganish imkoniyati."},
  {title:"Vaqtimni boshqaraman",task:"Ertangi kun uchun kichik reja tuz va eng muhim 3 vazifani belgilagin.",fields:[["morningPlan","Ertalab"],["afterSchool","Maktabdan keyin"],["eveningPlan","Kechqurun"],["beforeSleep","Uxlashdan oldin"],["topTasks","Ertangi eng muhim 3 vazifa"]],reflection:"Qaysi reja ertangi kunimni osonlashtiradi?",quote:"Reja — maqsadga olib boradigan xarita."},
  {title:"Bir yaxshilik",task:"Bugun hech kim so'ramasdan bitta yaxshilik qil.",fields:[["kindness","Qanday yaxshilik qildim?"]],reflection:"Men qilgan yaxshilik boshqa odamga qanday ta'sir qildi?",quote:"Dunyoni o'zgartirish kichik yaxshiliklardan boshlanadi."},
  {title:"Men qancha o'zgardim?",task:"Birinchi 20 kunni o'ylab, o'rganganlaring va yutuqlaringni qayd et.",fields:[["learned","Nimalarni o'rgandim?"],["newHabit","Qaysi yaxshi odatim paydo bo'ldi?"],["bigWin","Eng katta yutug'im"],["hardest","Eng qiyin vazifam"],["newAboutMe","O'zim haqimda bilgan yangi narsam"],["nextTen","Keyingi 10 kun uchun maqsadim"]],reflection:"Hozirgacha qaysi o'zgarishim bilan faxrlanaman?",quote:"O'sishingni sezish uchun ortga qarab ko'r."},
  {title:"Mening orzularim",task:"Kelajakda erishmoqchi bo'lgan 5 ta orzuingni yoz.",fields:[["dream1","1-orzu"],["dream2","2-orzu"],["dream3","3-orzu"],["dream4","4-orzu"],["dream5","5-orzu"],["smallStep","Bugun qila oladigan kichik qadam"]],reflection:"Agar muvaffaqiyatsizlikdan qo'rqmaganimda, nimaga harakat qilgan bo'lardim?",quote:"Katta orzular kichik qadamlardan boshlanadi."},
  {title:"Men qiyinchiliklarni yenga olaman",task:"Senga qiyin bo'lgan bir vaziyatni esla va undan qanday o'tganingni yoz.",fields:[["challenge","Muammo yoki vaziyat"],["feeling","O'sha paytda qanday his qilganman?"],["overcome","Undan qanday chiqdim?"],["smallChallenge","Bugun kechiktirmasdan bajaradigan kichik ish"]],reflection:"Men o'ylaganimdan kuchliroq ekanimni qachon sezganman?",quote:"Qiyinchiliklar — o'zing haqingda yangi narsalarni bilish imkoniyati."},
  {title:"Tanlovlarim",task:"Do'stlaring dars qilish o'rniga telefon o'ynashga chaqirsa, qanday qaror qilishingni o'yla.",fields:[["choice","Mening tanlovim va sababi"],["goodChoice","Bugun qiladigan bitta yaxshi tanlovim"]],reflection:"To'g'ri tanlov qilish nega ba'zida qiyin?",quote:"Kelajaging bugungi tanlovlaringdan quriladi."},
  {title:"Mening ijodkor tomonim",task:"O'zing yaratgan biror narsa qil: rasm, she'r, hikoya, video, poster yoki boshqa narsa.",fields:[["create","Bugun yaratgan narsam"],["idea1","Agar maktab direktori bo'lsam — 1-g'oya"],["idea2","2-g'oya"],["idea3","3-g'oya"]],reflection:"Men nimani yaratishni yaxshi ko'raman?",quote:"Ijodkorlik — boshqalar ko'rmagan imkoniyatni ko'ra olish."},
  {title:"Mening ovozim bor",task:"Bugun o'z fikringni hurmat bilan bildirishga harakat qil.",fields:[["opinion","Menimcha, maktabimizda ... yaxshiroq bo'lishi mumkin, chunki ..."],["expressed","Fikrimni qachon va qanday bildirdim?"]],reflection:"Boshqalarning fikridan farqli fikr bildirishdan qo'rqamanmi? Nega?",quote:"Sening fikring muhim. Uni hurmat bilan ifodalashni o'rgan."},
  {title:"Men lider bo'la olaman",task:"Sinfingda yoki oilangda boshqalarga yordam beradigan kichik liderlik ishini qil.",fields:[["leadershipAct","Bugun qilgan liderlik ishim"],["leader1","Yaxshi liderning 1-sifati"],["leader2","2-sifati"],["leader3","3-sifati"],["leaderVision","Men qanday lider bo'lishni xohlayman?"]],reflection:"Lider bo'lish uchun qaysi sifatni rivojlantirishim kerak?",quote:"Liderlik buyruq berish emas — yaxshi namuna bo'lish."},
  {title:"O'zimga mehr bilan",task:"Bir kun davomida o'zingni boshqalar bilan solishtirmaslikka harakat qil.",fields:[["selfValue","O'zimdagi qaysi jihatni qadrlashim kerak?"],["selfLetter","Aziz men, men sendagi ... ni qadrlayman, chunki ..."]],reflection:"O'zimga qanday mehr va hurmat ko'rsata olaman?",quote:"O'zingni qadrlash — mukammal bo'lish degani emas."},
  {title:"Mening o'rganish usulim",task:"O'zingga mos o'rganish usulini tanla va 20 daqiqa diqqat bilan shug'ullan.",fields:[["studyMethod","Menga yordam beradigan usul"],["phonePlan","Fokus paytida telefonni qanday boshqardim?"],["studyFormula","Mening o'rganish formulam: ... + ... + ..."]],reflection:"Men eng yaxshi qanday o'rganaman?",quote:"Aqlli bo'lishdan tashqari, qanday o'rganishni bilish ham muhim."},
  {title:"Kelajakdagi o'zimga xat",task:"3 yil keyingi o'zingga xat yoz.",fields:[["futureAge","Hozir men ... yoshdaman"],["futureDream","Men hozir ... haqida orzu qilaman"],["futureSelf","Kelajakda ... bo'lishni xohlayman"],["futureHope","Umid qilamanki, sen ... ga erishgansan"],["futureEffort","Men hozir sen uchun ... qilishga harakat qilyapman"],["futureRemember","Hech qachon ... ni unutma"]],reflection:"Kelajakdagi men bugungi menga qanday maslahat bergan bo'lardi?",quote:"Kelajakdagi sen bugungi kichik harakatlaring uchun rahmat aytadi."},
  {title:"Mening 30 kunlik sayohatim",task:"Tabriklaymiz! 30 kunlik yo'lingni yakunlab, o'zgarishlaringni qayd et.",fields:[["books","O'qigan kitoblarim"],["habitResult","Shakllantirgan yaxshi odatim"],["strengthResult","Rivojlantirgan kuchli tomonim"],["kindnessResult","Qilgan eng yaxshi ishim"],["lessonResult","O'rgangan eng muhim narsam"],["achievement","Eng katta yutug'im"],["beforeNow","Oldin qanday edim va hozir qandayman?"],["nextReading","Keyingi 30 kun uchun o'qish maqsadim"],["nextKnowledge","Bilim maqsadim"],["nextPersonal","Shaxsiy maqsadim"],["nextHabit","Yangi yaxshi odatim"]],reflection:"Ushbu 30 kun ichida o'zim bilan eng ko'p nimadan faxrlanaman?",quote:"30 kun tugadi. Lekin sening rivojlanishing davom etadi."}
];

var moodLabels = {1:"Juda og'ir", 2:"Unchalik yaxshi emas", 3:"O'rtacha", 4:"Yaxshi", 5:"Ajoyib"};
var currentDay = 1;
var entries = window.INITIAL_ENTRIES || {};
var mood = 0, rating = 0, answers = {};

function $(id) { return document.getElementById(id); }

function esc(s) {
  return String(s).replace(/[&<>"']/g, function(c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  });
}

function renderSelector() {
  $('day-selector').innerHTML = days.map(function(d, i) {
    var n = i + 1;
    var sel  = n === currentDay ? 'selected' : '';
    var done = (entries[n] && entries[n].completed) ? 'done' : '';
    var locked = isDayLocked(n) ? 'locked' : '';
    var check = (entries[n] && entries[n].completed) ? '<i>\u2713</i>' : '';
    var lockIcon = isDayLocked(n) ? '<i>\uD83D\uDD12</i>' : '';
    var title = isDayLocked(n) ? ' title="' + (n-1) + '-kunni yakunlagin"' : '';
    return '<button type="button" class="day-chip ' + sel + ' ' + done + ' ' + locked + '" data-day="' + n + '"' + title + '><span>' + String(n).padStart(2,'0') + '</span>' + (check || lockIcon) + '</button>';
  }).join('');
}

function renderFields() {
  var d = days[currentDay - 1];
  $('day-title').textContent = currentDay + '-kun: ' + d.title;
  $('day-pill').textContent = 'KUN ' + String(currentDay).padStart(2,'0') + ' / 30';
  $('task-text').textContent = d.task;
  $('reflection-prompt').textContent = d.reflection;
  $('daily-quote').textContent = d.quote;
  $('dynamic-fields').innerHTML = d.fields.map(function(f) {
    var key = f[0], label = f[1];
    var rows = label.length > 42 ? 3 : 2;
    return '<div class="field-group"><label for="f-' + key + '">' + esc(label) + '</label>' +
           '<textarea id="f-' + key + '" data-key="' + key + '" rows="' + rows + '" placeholder="Javobingni yoz...">' +
           esc(answers[key] || '') + '</textarea></div>';
  }).join('');
  $('reflection').value = answers._reflection || '';
  $('proud').value = answers._proud || '';
  document.querySelectorAll('[data-mood]').forEach(function(b) {
    b.classList.toggle('chosen', Number(b.dataset.mood) === mood);
  });
  document.querySelectorAll('[data-rating]').forEach(function(b) {
    b.classList.toggle('active', Number(b.dataset.rating) <= rating);
  });
  var isCompleted = !!(entries[currentDay] && entries[currentDay].completed);
  $('complete-btn').classList.toggle('completed', isCompleted);
  $('complete-btn').innerHTML = isCompleted ? 'Yakunlandi \u2713' : 'Kunni yakunlash <span>\u2713</span>';
  renderSelector();
  renderCalendar();
  updateStats();
  updateDayImage(currentDay);
}

function collect() {
  document.querySelectorAll('#dynamic-fields [data-key]').forEach(function(el) {
    answers[el.dataset.key] = el.value;
  });
  answers._reflection = $('reflection').value;
  answers._proud = $('proud').value;
}

function loadDay(n) {
  collect();
  currentDay = n;
  var e = entries[n] || {};
  answers = Object.assign({}, e.answers || {});
  mood = e.mood || 0;
  rating = e.rating || 0;
  renderFields();

  var isPastCompleted = !!(e.completed);
  // Lock all inputs if this day is already completed
  document.querySelectorAll('.entry-form input, .entry-form textarea').forEach(function(el) {
    el.disabled = isPastCompleted;
    el.style.opacity = isPastCompleted ? '.6' : '';
    el.style.cursor  = isPastCompleted ? 'not-allowed' : '';
  });
  document.querySelectorAll('[data-mood],[data-rating]').forEach(function(b) {
    b.disabled = isPastCompleted;
    b.style.cursor = isPastCompleted ? 'not-allowed' : '';
  });
  $('save-btn').disabled     = isPastCompleted;
  $('complete-btn').disabled = isPastCompleted;
  if (isPastCompleted) {
    $('save-btn').style.opacity     = '.45';
    $('complete-btn').style.opacity = '.45';
    $('save-status').textContent    = '🔒 Bu kun yakunlangan — tahrirlash mumkin emas.';
  } else {
    $('save-btn').style.opacity     = '';
    $('complete-btn').style.opacity = '';
    $('save-status').textContent    = 'Javoblaringni saqlashni unutma.';
  }

  document.querySelectorAll('.day-chip').forEach(function(b) {
    b.classList.toggle('selected', Number(b.dataset.day) === n);
  });
}

async function saveEntry(completed) {
  collect();
  if (completed === undefined) completed = false;
  var alreadyDone = !!(entries[currentDay] && entries[currentDay].completed);
  var data = { mood: mood, rating: rating, answers: answers, completed: completed || alreadyDone };
  $('save-status').textContent = 'Saqlanmoqda\u2026';
  try {
    var res = await fetch('/api/entry/' + currentDay, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('save');
    entries[currentDay] = Object.assign({}, data, {
      completed: data.completed,
      entry_date: new Date().toISOString().slice(0, 10)
    });
    $('save-status').textContent = data.completed
      ? '\u2713 Kun yakunlandi va saqlandi.'
      : '\u2713 Javoblar saqlandi.';
    renderSelector();
    renderCalendar();
    updateStats();
    $('complete-btn').classList.toggle('completed', data.completed);
    $('complete-btn').innerHTML = data.completed
      ? 'Yakunlandi \u2713'
      : 'Kunni yakunlash <span>\u2713</span>';
  } catch(err) {
    $('save-status').textContent = 'Saqlab bo\u02bclmadi. Internet yoki serverni tekshirib, qayta urin.';
  }
}

function renderCalendar() {
  var names = ['Du','Se','Ch','Pa','Ju','Sh','Ya'];
  var html = names.map(function(n) {
    return '<div class="calendar-day-name">' + n + '</div>';
  }).join('');
  html += days.map(function(d, i) {
    var n = i + 1;
    var e = entries[n] || {};
    var done   = e.completed ? 'calendar-done' : '';
    var sel    = n === currentDay ? 'calendar-selected' : '';
    var locked = isDayLocked(n) ? 'calendar-locked' : '';
    var icon   = e.completed ? '<i>\u2713</i>' : (isDayLocked(n) ? '<i style="font-size:9px">🔒</i>' : '');
    var titleAttr = isDayLocked(n) ? ' title="' + (n-1) + '-kunni yakunlagin"' : ' title="' + esc(d.title) + '"';
    return '<button type="button" class="calendar-day ' + done + ' ' + sel + ' ' + locked + '" data-calendar="' + n + '"' + titleAttr + '><span>' + String(n).padStart(2,'0') + '</span>' + icon + '</button>';
  }).join('');
  $('calendar-grid').innerHTML = html;
  var count = Object.values(entries).filter(function(e) { return e.completed; }).length;
  $('calendar-summary').textContent = count + ' / 30 kun yakunlangan';
}

function updateStats() {
  var completed = Object.values(entries).filter(function(e) { return e.completed; }).length;
  var ratings   = Object.values(entries).filter(function(e) { return e.rating > 0; }).map(function(e) { return e.rating; });
  var pct = Math.round(completed / 30 * 100);
  $('main-progress').style.width = pct + '%';
  $('progress-count').textContent = completed + ' / 30 kun yakunlandi';
  $('progress-percent').textContent = pct + '%';
  $('art-completed').textContent = String(completed).padStart(2,'0');
  $('mini-percent').textContent = pct + '%';
  $('mini-done').textContent = completed + ' kun';
  $('remaining-days').textContent = 30 - completed;
  $('average-rating').textContent = ratings.length
    ? (ratings.reduce(function(a,b){return a+b;}, 0) / ratings.length).toFixed(1) + ' / 5'
    : '— / 5';
}

document.addEventListener('click', function(e) {
  var chip = e.target.closest('[data-day]');
  if (chip) {
    var dayNum = Number(chip.dataset.day);
    if (isDayLocked(dayNum)) {
      $('save-status').textContent = '🔒 ' + (dayNum - 1) + '-kunni avval yakunlagin.';
      chip.classList.add('shake');
      setTimeout(function() { chip.classList.remove('shake'); }, 500);
      return;
    }
    loadDay(dayNum);
    return;
  }
  var cal = e.target.closest('[data-calendar]');
  if (cal) {
    var calNum = Number(cal.dataset.calendar);
    if (isDayLocked(calNum)) {
      $('save-status').textContent = '🔒 ' + (calNum - 1) + '-kunni avval yakunlagin.';
      return;
    }
    loadDay(calNum);
    document.getElementById('today').scrollIntoView({ behavior: 'smooth' });
    return;
  }
  var mb = e.target.closest('[data-mood]');
  if (mb) {
    mood = Number(mb.dataset.mood);
    document.querySelectorAll('[data-mood]').forEach(function(b) {
      b.classList.toggle('chosen', b === mb);
    });
    return;
  }
  var rb = e.target.closest('[data-rating]');
  if (rb) {
    rating = Number(rb.dataset.rating);
    document.querySelectorAll('[data-rating]').forEach(function(b) {
      b.classList.toggle('active', Number(b.dataset.rating) <= rating);
    });
    return;
  }
});

$('save-btn').addEventListener('click', function() { saveEntry(false); });
$('complete-btn').addEventListener('click', function() { saveEntry(true); });

var now = new Date();
$('today-date').textContent = now.toLocaleDateString('uz-UZ', { weekday:'long', day:'numeric', month:'long' });

renderFields();
showQuoteModal();
