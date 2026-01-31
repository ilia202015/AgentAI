import pytest
import os
import shutil
import plugins.web_interface.storage as storage
import plugins.web_interface.serialization as serialization
from google.genai import types

def test_migration_v1(mock_agent):
    """Verify that we can load the Golden Master v1.pkl."""
    # Copy baseline to the test chats directory
    source_pkl = "tests/data/v1.pkl"
    source_json = "tests/data/v1.json"
    
    shutil.copy(source_pkl, os.path.join(storage.CHATS_DIR, "v1.pkl"))
    shutil.copy(source_json, os.path.join(storage.CHATS_DIR, "v1.json"))
    
    # Load state
    chat, warning = storage.load_chat_state("v1", lambda: mock_agent)
    
    assert chat is not None
    assert chat.id == "v1"
    assert chat.name == "Baseline Chat v1"
    assert len(chat.messages) == 2
    
    # Check Message 1 (User + Image)
    msg1 = chat.messages[0]
    assert msg1.role == "user"
    assert "Hello with image" in msg1.parts[0].text
    # Image part check (in native format it's Part with inline_data)
    assert any(p.inline_data is not None for p in msg1.parts)

    # Check Message 2 (Model + Thoughts + Tools)
    msg2 = chat.messages[1]
    assert msg2.role == "model"
    # Note: in Pickle thoughts might be in parts or in _web_thoughts
    thoughts = getattr(msg2, "_web_thoughts", "")
    if not thoughts:
        thoughts = "\n".join([p.text for p in msg2.parts if getattr(p, "thought", False)])
    
    assert "Baseline thoughts" in thoughts or "Thinking..." in thoughts
    assert len(msg2._web_tools) == 1
    assert msg2._web_tools[0]["title"] == "python"

def test_pickle_json_equivalence(mock_agent):
    """Verify that data loaded from JSON backup is equivalent to Pickle (where possible)."""
    # 1. Setup baseline
    shutil.copy("tests/data/v1.pkl", os.path.join(storage.CHATS_DIR, "v1.pkl"))
    shutil.copy("tests/data/v1.json", os.path.join(storage.CHATS_DIR, "v1.json"))
    
    # 2. Force load from Pickle
    chat_pkl, _ = storage.load_chat_state("v1", lambda: mock_agent)
    
    # 3. Force load from JSON (by removing PKL temporarily)
    os.remove(os.path.join(storage.CHATS_DIR, "v1.pkl"))
    chat_json, _ = storage.load_chat_state("v1", lambda: mock_agent)
    
    assert chat_pkl.name == chat_json.name
    assert len(chat_pkl.messages) == len(chat_json.messages)
    
    # Compare roles and text content
    for m_pkl, m_json in zip(chat_pkl.messages, chat_json.messages):
        assert m_pkl.role == m_json.role
        
        # In JSON, thoughts are moved from parts to _web_thoughts
        texts_pkl = [p.text for p in m_pkl.parts if p.text and not getattr(p, "thought", False)]
        texts_json = [p.text for p in m_json.parts if p.text]
        assert texts_pkl == texts_json
        
        # Check thoughts equivalence
        thoughts_pkl = getattr(m_pkl, "_web_thoughts", "")
        if not thoughts_pkl:
            thoughts_pkl = "\n".join([p.text for p in m_pkl.parts if getattr(p, "thought", False)])
            
        thoughts_json = getattr(m_json, "_web_thoughts", "")
        assert thoughts_pkl.strip() == thoughts_json.strip()

def test_serialization_cycle(mock_agent):
    """Verify a full save/load cycle for complex multimodal data."""
    chat = mock_agent
    chat.id = "cycle_test"
    
    # Create a message with thoughts and an image
    msg = types.Content(
        role="model",
        parts=[
            types.Part(text="Thinking about a cat...", thought=True),
            types.Part(text="Here is a cat:"),
            types.Part.from_bytes(data=b"cat_image_data", mime_type="image/jpeg")
        ]
    )
    msg._web_thoughts = "I like cats"
    msg._web_tools = [{"title": "vision", "content": "cat detected"}]
    chat.messages.append(msg)
    
    # Save
    storage.save_chat_state(chat)
    
    # Load back
    loaded_chat, _ = storage.load_chat_state("cycle_test", lambda: mock_agent)
    
    assert len(loaded_chat.messages) == 1
    loaded_msg = loaded_chat.messages[0]
    
    assert loaded_msg.role == "model"
    assert loaded_msg._web_thoughts == "I like cats"
    assert loaded_msg._web_tools[0]["title"] == "vision"
    
    # Verify image integrity
    img_parts = [p for p in loaded_msg.parts if p.inline_data]
    assert len(img_parts) == 1
    assert img_parts[0].inline_data.data == b"cat_image_data"
