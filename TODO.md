[todo] Feature1: 新增测试 agent，该 agent 封装 Playwright 实现 web 页面的测试。
> 说明，具体实现部分，需要参考 Playwright 的说明文档 https://playwright.dev/docs/intro
step1: 创建 Playwright 的docker容器;
step2: 将 Playwright 服务封装为 mcp service。
step3：读取测试用例文档 test-case.xlsx;
step4 读取测试用例文档生成测试脚本；
step5: 使用命令 /agent test-ui test-case.xlsx;