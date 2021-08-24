def test_webhook(anon, load_json):
    anon.post(
        '/api/bot/github',
        load_json('issue_comment_payload.json'),
        **{'HTTP_X_GITHUB_EVENT': 'issue_comment'},
    )
