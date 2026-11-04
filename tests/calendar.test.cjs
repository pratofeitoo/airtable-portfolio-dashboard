const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('index.html','utf8');
const calendar=html.split('/* calendar-start */')[1].split('/* calendar-end */')[0];
const context=vm.createContext({Intl,Date});vm.runInContext(calendar,context);
test('São Paulo date does not advance at UTC midnight',()=>{assert.equal(context.saoPauloDay(new Date('2026-11-05T01:00:00Z')),'2026-11-04')});
test('rolling windows cross months, years and leap days',()=>{assert.equal(context.addDays('2026-12-29',7),'2027-01-05');assert.equal(context.addDays('2028-02-28',1),'2028-02-29')});
test('due buckets respect today and seven-day boundaries',()=>{for(const [day,label] of [['','Sem prazo'],['2026-12-30','Atrasados'],['2026-12-31','Vencem hoje'],['2027-01-07','Próximos 7 dias'],['2027-01-08','Entre 8 e 30 dias'],['2027-01-31','Após 30 dias']])assert.equal(context.dueBucket(day,'2026-12-31'),label)});
