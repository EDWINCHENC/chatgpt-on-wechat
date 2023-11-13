                    elapsed_time = time.time() - start_time  # 计算耗时
                    # 仅在成功获取数据后发送信息
                    if context.kwargs.get('isgroup'):
                        msg = context.kwargs.get('msg')  # 这是WechatMessage实例
                        nickname = msg.actual_user_nickname  # 获取nickname
                        _send_info(e_context, f"@{nickname}\n✅联网获取AI资讯成功, 正在整理。🕒耗时{elapsed_time:.2f}秒")
                    else:
                        _send_info(e_context, f"✅联网获取AI资讯成功, 正在整理。🕒耗时{elapsed_time:.2f}秒")