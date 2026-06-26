class BroadcastBooth:

    def __init__(self):

        self.last_comment = ""

    def broadcast(self, commentary):

        if commentary == self.last_comment:
            return

        self.last_comment = commentary

        print()
        print("🎙 RGC BROADCAST")
        print("=" * 60)
        print(commentary)
        print("=" * 60)