import subprocess
import time
from urllib.parse import urlencode

import gradio as gr
from ddddocr import DdddOcr
from loguru import logger

from config import cookies_config_path
from geetest.api import Click
from geetest.click3 import Click3
from util.bili_request import BiliRequest


def train_tab():
    gr.Markdown("""
> **补充**
>
> 在这里，你可以
> 1. 提前知道抢票时候验证码的过程
> 2. 训练验证码，提高验证码速度
>
""")
    _request = BiliRequest(cookies_config_path=cookies_config_path)

    gr.Markdown("💪 在这里训练一下手过验证码的速度，提前演练一下")
    test_get_challenge_btn = gr.Button("开始测试")
    test_log = gr.JSON(label="测试结果（验证码过期是正常现象）")

    with gr.Row(visible=False) as test_gt_row:
        test_gt_html_start_btn = gr.Button("点击打开抢票验证码（请勿多点！！）")
        test_gt_ai_start_btn = gr.Button("点击AI自动过验证码（测试功能不保证正确性）")
        test_gt_html_finish_btn = gr.Button("完成验证码后点此此按钮")
        gr.HTML(
            value="""
                <div>
                    <label>如何点击无效说明，获取验证码失败，请勿多点</label>
                    <div id="captcha_test" />
                </div>
                """,
            label="验证码",
        )
    test_gt_ui = gr.Textbox(label="gt", visible=True)
    test_challenge_ui = gr.Textbox(label="challenge", visible=True)
    geetest_result = gr.JSON(label="validate")

    def test_get_challenge():
        global \
            test_challenge, \
            test_gt, \
            test_token, \
            test_csrf, \
            test_geetest_validate, \
            test_geetest_seccode
        test_res = _request.get(
            "https://passport.bilibili.com/x/passport-login/captcha?source=main_web"
        ).json()
        test_challenge = test_res["data"]["geetest"]["challenge"]
        test_gt = test_res["data"]["geetest"]["gt"]
        test_token = test_res["data"]["token"]
        test_csrf = _request.cookieManager.get_cookies_value("bili_jct")
        test_geetest_validate = ""
        test_geetest_seccode = ""
        return [
            gr.update(value=test_gt),  # test_gt_ui
            gr.update(value=test_challenge),  # test_challenge_ui
            gr.update(visible=True),  # test_gt_row
            gr.update(value="重新生成"),  # test_get_challenge_btn
        ]

    test_get_challenge_btn.click(
        fn=test_get_challenge,
        inputs=None,
        outputs=[test_gt_ui, test_challenge_ui, test_gt_row, test_get_challenge_btn],
    )

    def gt_auto_complete(gt, challenge):
        global test_geetest_validate, test_geetest_seccode
        api = Click()
        rt = "1234567890123456"
        click3 = Click3(DdddOcr(show_ad=False, beta=True))
        (c, s) = api.get_c_s(challenge, gt, None)
        api.get_type(challenge, gt, None)
        (c, s, pic) = api.get_new_c_s_pic(challenge, gt)
        position = click3.calculated_position(pic)
        cmd3 = f"node -e \"require('./geetest/click.js').send('{gt}','{challenge}',{c},'{s}','{rt}','{position}')\""
        w = subprocess.run(cmd3, shell=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
        time.sleep(2)
        res = api.ajax(challenge, gt, w)
        logger.info(res)
        if res['data']['result'] == 'success':
            test_geetest_validate = res['data']['validate']
            test_geetest_seccode = res['data']['validate'] + "|jordan"
            _url = "https://api.bilibili.com/x/gaia-vgate/v1/validate"
            _payload = {
                "challenge": test_challenge,
                "token": test_token,
                "seccode": test_geetest_seccode,
                "csrf": test_csrf,
                "validate": test_geetest_validate,
            }
            test_data = _request.post(_url, urlencode(_payload))
            yield gr.update(value=test_data.json())
        else:
            yield gr.update(value=res)

    test_gt_ai_start_btn.click(
        fn=gt_auto_complete,
        inputs=[test_gt_ui, test_challenge_ui],
        outputs=[test_log],
    )
    test_gt_html_start_btn.click(
        fn=None,
        inputs=[test_gt_ui, test_challenge_ui],
        outputs=None,
        js="""
            (gt, challenge) => initGeetest({
                gt, challenge,
                offline: false,
                new_captcha: true,
                product: "popup",
                width: "300px",
                https: true
            }, function (test_captchaObj) {
                window.test_captchaObj = test_captchaObj;
                $('#captcha_test').empty();
                test_captchaObj.appendTo('#captcha_test');
            })
            """,
    )

    test_gt_html_finish_btn.click(
        fn=None,
        inputs=None,
        outputs=geetest_result,
        js="() => test_captchaObj.getValidate()",
    )

    def receive_geetest_result(res):
        global test_geetest_validate, test_geetest_seccode
        test_geetest_validate = res["geetest_validate"]
        test_geetest_seccode = res["geetest_seccode"]

    geetest_result.change(fn=receive_geetest_result, inputs=geetest_result)

    def test_doing():
        while test_geetest_validate == "" or test_geetest_seccode == "":
            continue
        _url = "https://api.bilibili.com/x/gaia-vgate/v1/validate"
        _payload = {
            "challenge": test_challenge,
            "token": test_token,
            "seccode": test_geetest_seccode,
            "csrf": test_csrf,
            "validate": test_geetest_validate,
        }
        test_data = _request.post(_url, urlencode(_payload))
        yield gr.update(value=test_data.json())

    test_gt_html_finish_btn.click(fn=test_doing, outputs=[test_log])
