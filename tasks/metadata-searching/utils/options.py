class options(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except Exception as ex:
            print(f"Error: {ex}")
            return None
