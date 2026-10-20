class Strategy:
    def on_start(self, params):
        pass

    def on_bar(self, context, bar):
        return None

    def on_end(self, params):
        pass
