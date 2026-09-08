const playwrightModule=process.env.PLAYWRIGHT_MODULE || 'playwright';
const {chromium}=require(playwrightModule);
const baseUrl=process.env.DASHBOARD_URL || 'http://127.0.0.1:8502';
const channel=process.env.PLAYWRIGHT_CHANNEL;

(async()=>{
  const browser=await chromium.launch({headless:true,...(channel?{channel}:{})});
  try {
    const page=await browser.newPage({viewport:{width:1600,height:1100},deviceScaleFactor:1});
    await page.goto(baseUrl);
    await page.getByRole('heading',{name:'在线零售收入质量、客户留存与退货分析',exact:true}).waitFor({timeout:45000});
    await page.getByRole('button',{name:'Stop',exact:true}).waitFor({state:'hidden',timeout:45000});
    await page.screenshot({path:'reports/dashboard-overview.png',fullPage:true});
    await page.getByRole('tab',{name:'客户与留存',exact:true}).click();
    await page.getByText('RFM 客户分层',{exact:true}).waitFor();
    await page.screenshot({path:'reports/dashboard-customers.png',fullPage:true});
    await page.getByRole('tab',{name:'商品与退货',exact:true}).click();
    await page.getByText('净收入最高的商品',{exact:true}).waitFor();
    await page.screenshot({path:'reports/dashboard-products.png',fullPage:true});
    console.log(JSON.stringify({status:'captured',screenshots:3}));
  } finally {
    await browser.close();
  }
})().catch(error=>{console.error(error);process.exit(1)});
