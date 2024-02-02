from app import app, init_app_context

if __name__ == "__main__":
	init_app_context(app)
	app.run()
