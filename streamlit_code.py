# # import streamlit as st
# # import requests
# # import os

# # # -------------------- SESSION STATE INIT --------------------
# # if "info_messages" not in st.session_state:
# #     st.session_state.info_messages = []

# # if "grievance_messages" not in st.session_state:
# #     st.session_state.grievance_messages = []

# # # -------------------- CONFIG --------------------
# # st.set_page_config(page_title="Chat & Grievance Portal", layout="wide")

# # BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://10.40.108.197:8508")
# # DEFAULT_USER_ID  = os.getenv("DEFAULT_USER_ID", "demo_user")

# # CHAT_URL      = f"{BACKEND_BASE_URL}/chat"
# # GRIEVANCE_URL = f"{BACKEND_BASE_URL}/chat/grievance"



# # def call_backend_grievance(url, user_message):
# #     payload = {
# #         "user_id": DEFAULT_USER_ID,
# #         "message": user_message
# #     }

# #     try:
# #         r = requests.post(url, json=payload, timeout=20)
# #         try:
# #             return r.json()   # always return full JSON body
# #         except:
# #             return {"message": r.text}
# #     except Exception as e:
# #         return {"message": f"Connection error: {e}"}

# # # -------------------- BACKEND CALLER --------------------
# # def call_backend(url, user_message):
# #     payload = {
# #         "user_id": DEFAULT_USER_ID,
# #         "message": user_message
# #     }

# #     try:
# #         r = requests.post(url, json=payload, timeout=20)
# #         try:
# #             body = r.json()
# #         except:
# #             body = r.text

# #         # If JSON → extract first string value
# #         if isinstance(body, dict):
# #             for v in body.values():
# #                 if isinstance(v, str):
# #                     return v
# #             return str(body)

# #         return body

# #     except Exception as e:
# #         return f"<p style='color:red'>Connection error: {e}</p>"

# # st.title("Uttar Pradesh AI Chatbot")
# # st.write("Choose Service")
# # # -------------------- UI TABS --------------------
# # tab1, tab2 = st.tabs(["🤖 Information Bot", "📢 Raise Grievance"])


# # # -------------------- INFORMATION BOT TAB --------------------
# # with tab1:
# #     st.subheader("Information Bot")

# #     info_input = st.chat_input("Ask something...")

# #     if info_input:
# #         st.session_state.info_messages.append({"role": "user", "content": info_input})
# #         reply = call_backend(CHAT_URL, info_input)
# #         st.session_state.info_messages.append({"role": "assistant", "content": reply})

# #     for msg in st.session_state.info_messages:
# #         with st.chat_message(msg["role"]):
# #             st.markdown(msg["content"], unsafe_allow_html=True)



# # # -------------------- GRIEVANCE BOT TAB --------------------
# # with tab2:
# #     st.subheader("Raise a Grievance")

# #     # Display existing messages
# #     messages_container = st.container()
# #     with messages_container:
# #         for msg in st.session_state.grievance_messages:
# #             with st.chat_message(msg["role"]):
# #                 st.markdown(msg["content"], unsafe_allow_html=True)

# #     # Input stays at bottom
# #     grievance_input = st.chat_input("Describe your grievance...")

# #     if grievance_input:

# #         # Save user message
# #         st.session_state.grievance_messages.append({
# #             "role": "user",
# #             "content": grievance_input
# #         })

# #         # Call backend API
# #         response = call_backend_grievance(GRIEVANCE_URL, grievance_input)

# #         status  = response.get("status")
# #         message = response.get("message", "")
# #         ticket  = response.get("grievance_id")

# #         # ---------- SUCCESS HANDLING ----------
# #         if status == "success":
# #             # Show final success message
# #             success_text = f"""
# #             <div style='padding:10px;border-left:4px solid green;'>
# #                 <b>✅ Your grievance has been registered successfully!</b><br>
# #                 Ticket Number: <b>{ticket}</b>
# #             </div>
# #             """
# #             st.session_state.grievance_messages.append({
# #                 "role": "assistant",
# #                 "content": success_text
# #             })

# #         else:
# #             # ---------- FAILURE HANDLING ----------
# #             # Show normal message (ask for more info)
# #             st.session_state.grievance_messages.append({
# #                 "role": "assistant",
# #                 "content": message
# #             })

# #         # Refresh to update UI smoothly
# #         st.rerun()

# import streamlit as st
# import requests
# import os

# # -------------------- SESSION STATE INIT --------------------
# if "info_messages" not in st.session_state:
#     st.session_state.info_messages = []

# if "grievance_messages" not in st.session_state:
#     st.session_state.grievance_messages = []

# # -------------------- CONFIG --------------------
# st.set_page_config(page_title="Chat & Grievance Portal", layout="wide")

# BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://10.40.108.197:8508")
# DEFAULT_USER_ID  = os.getenv("DEFAULT_USER_ID", "demo_user")

# # Use the streaming endpoint you added in FastAPI
# CHAT_URL      = f"{BACKEND_BASE_URL}/chat/stream"
# GRIEVANCE_URL = f"{BACKEND_BASE_URL}/chat/grievance"


# def call_backend_grievance(url, user_message):
#     payload = {
#         "user_id": DEFAULT_USER_ID,
#         "message": user_message
#     }

#     try:
#         r = requests.post(url, json=payload, timeout=20)
#         try:
#             return r.json()   # always return full JSON body
#         except:
#             return {"message": r.text}
#     except Exception as e:
#         return {"message": f"Connection error: {e}"}

# # -------------------- Non-streaming fallback (kept for reference, unused now) --------------------
# def call_backend(url, user_message):
#     payload = {
#         "user_id": DEFAULT_USER_ID,
#         "message": user_message
#     }
#     try:
#         r = requests.post(url, json=payload, timeout=20)
#         try:
#             body = r.json()
#         except:
#             body = r.text

#         if isinstance(body, dict):
#             for v in body.values():
#                 if isinstance(v, str):
#                     return v
#             return str(body)
#         return body
#     except Exception as e:
#         return f"<p style='color:red'>Connection error: {e}</p>"

# # -------------------- NEW: Streaming helper --------------------
# def stream_backend_text(url, user_message):
#     """
#     Streams chunks from backend using HTTP chunked response.
#     Yields small text pieces as they arrive.
#     """
#     payload = {"user_id": DEFAULT_USER_ID, "message": user_message}
#     try:
#         with requests.post(url, json=payload, timeout=180, stream=True) as r:
#             r.raise_for_status()
#             for chunk in r.iter_content(chunk_size=1024):
#                 if not chunk:
#                     continue
#                 text = chunk.decode("utf-8", errors="ignore")
#                 if text:
#                     yield text
#     except Exception as e:
#         yield f"\n\n**(Note)**: Streaming not available. Error: {e}"

# def stream_backend_text(url, user_message):
#     """
#     Streams chunks from backend using HTTP chunked response.
#     Yields small text pieces as they arrive.
#     """
#     payload = {"user_id": DEFAULT_USER_ID, "message": user_message}
#     try:
#         with requests.post(url, json=payload, timeout=180, stream=True) as r:
#             r.raise_for_status()
#             for chunk in r.iter_content(chunk_size=1024):
#                 if not chunk:
#                     continue
#                 text = chunk.decode("utf-8", errors="ignore")
#                 if text:
#                     yield text
#     except Exception as e:
#         # Show error in stream so you can debug
#         yield f"\n\n**(Note)**: Streaming not available. Error: {e}"

# # -------------------- UI --------------------
# st.title("Uttar Pradesh AI Chatbot")
# st.write("Choose Service")

# import sys, time  # at top of file if not already imported

# with tab1:
#     st.subheader("Information Bot")

#     # ✅ Toggle to see raw chunks exactly as they arrive
#     show_raw = st.checkbox(
#         "Show raw chunks (debug mode)",
#         value=True,
#         help="Print each chunk exactly as received from the backend."
#     )

#     # Render previous messages (for normal view history)
#     for msg in st.session_state.info_messages:
#         with st.chat_message(msg["role"]):
#             st.markdown(msg["content"], unsafe_allow_html=True)

#     info_input = st.chat_input("Ask something...")

#     if info_input:
#         # Save + render user message
#         st.session_state.info_messages.append({"role": "user", "content": info_input})
#         with st.chat_message("user"):
#             st.markdown(info_input, unsafe_allow_html=True)

#         with st.chat_message("assistant"):
#             if show_raw:
#                 # --- RAW CHUNKS MODE ---
#                 st.caption("Streaming **raw chunks** from server…")
#                 raw_container = st.container()
#                 chunks = []
#                 idx = 0

#                 for chunk in stream_backend_text(CHAT_URL, info_input):
#                     idx += 1
#                     chunks.append(chunk)

#                     # Log to console (optional but useful)
#                     print(f"[CHUNK #{idx}] {repr(chunk)}", file=sys.stderr, flush=True)

#                     # Show each chunk as its own line with index (debug clarity)
#                     with raw_container:
#                         st.markdown(f"**#{idx}** `{repr(chunk)}`")

#                 # Optional: show combined preview at the end
#                 st.divider()
#                 st.caption("Combined (preview):")
#                 st.code("".join(chunks))

#                 # Persist combined to history (so prior messages render normally)
#                 st.session_state.info_messages.append({
#                     "role": "assistant",
#                     "content": "".join(chunks)
#                 })

#             else:
#                 # --- NORMAL RENDERED MODE (stitches chunks into one answer) ---
#                 placeholder = st.empty()
#                 full_text = ""
#                 for chunk in stream_backend_text(CHAT_URL, info_input):
#                     full_text += chunk
#                     placeholder.markdown(full_text, unsafe_allow_html=True)
#                 st.session_state.info_messages.append({"role": "assistant", "content": full_text})

# # -------------------- GRIEVANCE BOT TAB (UNCHANGED) --------------------
# with tab2:
#     st.subheader("Raise a Grievance")

#     messages_container = st.container()
#     with messages_container:
#         for msg in st.session_state.grievance_messages:
#             with st.chat_message(msg["role"]):
#                 st.markdown(msg["content"], unsafe_allow_html=True)

#     grievance_input = st.chat_input("Describe your grievance...")

#     if grievance_input:
#         st.session_state.grievance_messages.append({
#             "role": "user",
#             "content": grievance_input
#         })

#         response = call_backend_grievance(GRIEVANCE_URL, grievance_input)

#         status  = response.get("status")
#         message = response.get("message", "")
#         ticket  = response.get("grievance_id")

#         if status == "success":
#             success_text = f"""
#             <div style='padding:10px;border-left:4px solid green;'>
#                 <b>✅ Your grievance has been registered successfully!</b><br>
#                 Ticket Number: <b>{ticket}</b>
#             </div>
#             """
#             st.session_state.grievance_messages.append({
#                 "role": "assistant",
#                 "content": success_text
#             })
#         else:
#             st.session_state.grievance_messages.append({
#                 "role": "assistant",
#                 "content": message
#             })

#         # Optional: you can keep st.rerun() if you prefer instant re-render
#         # st.rerun()




import streamlit as st
import requests
import os
import sys
import time

# -------------------- SESSION STATE INIT --------------------
if "info_messages" not in st.session_state:
    st.session_state.info_messages = []

if "grievance_messages" not in st.session_state:
    st.session_state.grievance_messages = []

# -------------------- CONFIG --------------------
st.set_page_config(page_title="Chat & Grievance Portal", layout="wide")

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://10.40.108.197:8508")
DEFAULT_USER_ID  = os.getenv("DEFAULT_USER_ID", "demo_user")

# IMPORTANT: Use the streaming endpoint in FastAPI
CHAT_URL      = f"{BACKEND_BASE_URL}/chat/stream"
GRIEVANCE_URL = f"{BACKEND_BASE_URL}/chat/grievance"


def call_backend_grievance(url, user_message):
    payload = {
        "user_id": DEFAULT_USER_ID,
        "message": user_message
    }
    try:
        r = requests.post(url, json=payload, timeout=20)
        try:
            return r.json()   # always return full JSON body
        except:
            return {"message": r.text}
    except Exception as e:
        return {"message": f"Connection error: {e}"}

# -------------------- (kept) Non-streaming helper (unused here, but OK to keep) --------------------
def call_backend(url, user_message):
    payload = {
        "user_id": DEFAULT_USER_ID,
        "message": user_message
    }
    try:
        r = requests.post(url, json=payload, timeout=20)
        try:
            body = r.json()
        except:
            body = r.text

        if isinstance(body, dict):
            for v in body.values():
                if isinstance(v, str):
                    return v
            return str(body)
        return body
    except Exception as e:
        return f"<p style='color:red'>Connection error: {e}</p>"

# -------------------- NEW: Streaming helper --------------------
def stream_backend_text(url, user_message):
    """
    Streams chunks from backend using HTTP chunked response.
    Yields small text pieces as they arrive.
    """
    payload = {"user_id": DEFAULT_USER_ID, "message": user_message}
    try:
        with requests.post(url, json=payload, timeout=180, stream=True) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=1024):
                if not chunk:
                    continue
                text = chunk.decode("utf-8", errors="ignore")
                if text:
                    yield text
    except Exception as e:
        # Show error in stream so you can debug
        yield f"\n\n**(Note)**: Streaming not available. Error: {e}"

# -------------------- UI --------------------
st.title("Uttar Pradesh AI Chatbot")
st.write("Choose Service")

# ✅ You must create tabs before using tab1/tab2
tab1, tab2 = st.tabs(["🤖 Information Bot", "📢 Raise Grievance"])

# -------------------- INFORMATION BOT TAB --------------------
with tab1:
    st.subheader("Information Bot")

    # Toggle to see raw chunks exactly as they arrive
    show_raw = st.checkbox(
        "Show raw chunks (debug mode)",
        value=True,
        help="Print each chunk exactly as received from the backend."
    )

    # Render previous messages for normal conversation view
    for msg in st.session_state.info_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

    info_input = st.chat_input("Ask something...")

    if info_input:
        # Save + render user message
        st.session_state.info_messages.append({"role": "user", "content": info_input})
        with st.chat_message("user"):
            st.markdown(info_input, unsafe_allow_html=True)

        with st.chat_message("assistant"):
            if show_raw:
                # --- RAW CHUNKS MODE ---
                st.caption("Streaming **raw chunks** from server…")
                raw_container = st.container()
                chunks = []
                idx = 0

                for chunk in stream_backend_text(CHAT_URL, info_input):
                    idx += 1
                    chunks.append(chunk)

                    # Log to console (optional but useful)
                    print(f"[CHUNK #{idx}] {repr(chunk)}", file=sys.stderr, flush=True)

                    # Show each chunk as its own line with index (debug clarity)
                    with raw_container:
                        st.markdown(f"**#{idx}** `{repr(chunk)}`")

                # Optional: show combined preview at the end
                st.divider()
                st.caption("Combined (preview):")
                st.code("".join(chunks))

                # Persist combined to history (so prior messages render normally)
                st.session_state.info_messages.append({
                    "role": "assistant",
                    "content": "".join(chunks)
                })

            else:
                # --- NORMAL RENDERED MODE (stitches chunks into one answer) ---
                placeholder = st.empty()
                full_text = ""
                for chunk in stream_backend_text(CHAT_URL, info_input):
                    full_text += chunk
                    placeholder.markdown(full_text, unsafe_allow_html=True)
                st.session_state.info_messages.append({"role": "assistant", "content": full_text})

# -------------------- GRIEVANCE BOT TAB --------------------
with tab2:
    st.subheader("Raise a Grievance")

    # Display existing messages
    for msg in st.session_state.grievance_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

    grievance_input = st.chat_input("Describe your grievance...")

    if grievance_input:
        # Save user message
        st.session_state.grievance_messages.append({
            "role": "user",
            "content": grievance_input
        })

        # Call backend API
        response = call_backend_grievance(GRIEVANCE_URL, grievance_input)

        status  = response.get("status")
        message = response.get("message", "")
        ticket  = response.get("grievance_id")

        if status == "success":
            # ✅ Use real HTML here (no &lt; &gt;) so it renders nicely
            success_text = f"""
            <div style='padding:10px;border-left:4px solid green;'>
                <b>✅ Your grievance has been registered successfully!</b><br>
                Ticket Number: <b>{ticket}</b>
            </div>
            """
            st.session_state.grievance_messages.append({
                "role": "assistant",
                "content": success_text
            })
        else:
            # Failure/ask for more info
            st.session_state.grievance_messages.append({
                "role": "assistant",
                "content": message
            })

        # Optional: rerun to force immediate re-render
        # st.rerun()
