from app import app, init_app_context

if __name__ == "wsgi":
	init_app_context(app)
	app.run()
