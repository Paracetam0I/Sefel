from app.core.paths import resourcePath, userDataPath

print("Templates:", resourcePath("templates"))
print("Existe:", resourcePath("templates").exists())
print("DB path:", userDataPath("data/app.db"))