import os
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GRPC_TRACE"] = ""

import google.generativeai as genai

genai.configure(api_key="AIzaSyBty25Wk61YWqe6FWaFgVeBn4uGawO-nSo")

for m in genai.list_models():
    print(m.name)
