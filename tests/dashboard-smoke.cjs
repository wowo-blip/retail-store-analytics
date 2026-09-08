const assert=require('assert');

const playwrightModule=process.env.PLAYWRIGHT_MODULE || 'playwright';
const {chromium}=require(playwrightModule);
const baseUrl=process.env.DASHBOARD_URL || 'http://127.0.0.1:8510';
const channel=process.env.PLAYWRIGHT_CHANNEL;
const expectedMode=process.env.EXPECT_MODE || 'demo';

async function openDashboard(page) {
  const deadline=Date.now()+60000;
  let lastError;
  while(Date.now()<deadline) {
    try {
      await page.goto(baseUrl,{waitUntil:'domcontentloaded',timeout:10000});
      return;
    } catch(error) {
      lastError=error;
      await new Promise(resolve=>setTimeout(resolve,1000));
    }
  }
  throw new Error(`Dashboard did not become reachable within 60 seconds: ${lastError}`);
}

(async()=>{
  const browser=await chromium.launch({headless:true,...(channel?{channel}:{})});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    const pageErrors=[];
    page.on('pageerror',error=>pageErrors.push(error.message));
    await openDashboard(page);
    await page.getByRole('heading',{name:'在线零售收入质量、客户留存与退货分析',exact:true}).waitFor({timeout:45000});
    if(expectedMode==='demo') {
      await page.getByText('当前为 DuckDB + Parquet 免 MySQL 演示',{exact:false}).waitFor({timeout:45000});
    }
    await page.getByText('£19.01M',{exact:true}).waitFor({timeout:45000});
    await page.getByRole('tab',{name:'数据质量',exact:true}).click();
    await page.getByRole('button',{name:'下载审计样本 CSV',exact:true}).waitFor({timeout:45000});
    assert.equal(await page.locator('[data-testid="stException"]').count(),0);
    assert.deepEqual(pageErrors,[]);
    console.log(JSON.stringify({status:'passed',mode:expectedMode,pageErrors}));
  } finally {
    await browser.close();
  }
})().catch(error=>{console.error(error);process.exit(1)});
