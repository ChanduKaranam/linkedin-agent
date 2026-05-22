import requests
import json
import sys

def main():
    base_url = "http://127.0.0.1:8000"
    session = requests.Session()
    
    # 1. Login
    print("1. Logging in...")
    login_url = f"{base_url}/auth/login"
    login_res = session.post(login_url, json={"username": "admin", "password": "admin123"})
    if login_res.status_code != 200:
        print(f"Login failed: {login_res.status_code} - {login_res.text}")
        sys.exit(1)
    print("Login successful:", login_res.json())
    
    # 2. Get today's trends
    print("\n2. Fetching today's trends...")
    trends_url = f"{base_url}/trends/by-date/2026-05-22"
    trends_res = session.get(trends_url)
    if trends_res.status_code != 200:
        print(f"Failed to fetch trends: {trends_res.status_code} - {trends_res.text}")
        sys.exit(1)
    
    trends = trends_res.json()
    print(f"Found {len(trends)} trends.")
    if not trends:
        print("No trends found, exiting.")
        sys.exit(1)
        
    trend = trends[0]
    slug = trend["slug"]
    print(f"Selected trend: {slug} - {trend['headline']}")
    
    # 3. Generate a daily LinkedIn post (leadership style)
    print(f"\n3. Generating daily LinkedIn post (leadership style) for {slug}...")
    generate_url = f"{base_url}/posts/2026-05-22/{slug}/linkedin"
    payload = {
        "user_instructions": "Keep it punchy",
        "style": "leadership"
    }
    gen_res = session.post(generate_url, json=payload)
    if gen_res.status_code != 201:
        print(f"Generation failed: {gen_res.status_code} - {gen_res.text}")
        sys.exit(1)
        
    post = gen_res.json()
    post_id = post["id"]
    print("Generated post:")
    print(f"  ID: {post_id}")
    print(f"  Kind: {post['kind']}")
    print(f"  Style Chosen: {post['style_chosen']}")
    print(f"  Evaluation Score: {post['evaluation']['score']}")
    print(f"  Strengths count: {len(post['evaluation']['strengths'])}")
    print(f"  Critique count: {len(post['evaluation']['critique'])}")
    print(f"  Suggestions count: {len(post['evaluation']['suggestions'])}")
    
    # 4. Patch post content (simulate editing)
    print(f"\n4. Simulating user edit for post {post_id}...")
    patch_url = f"{base_url}/posts/{post_id}"
    original_content = post["content_markdown"]
    modified_content = original_content + "\n\nThis is an added line to simulate user edits and trigger re-evaluation."
    
    patch_res = session.patch(patch_url, json={
        "content_markdown": modified_content,
        "tags": post["tags"]
    })
    if patch_res.status_code != 200:
        print(f"Patch failed: {patch_res.status_code} - {patch_res.text}")
        sys.exit(1)
        
    patched_post = patch_res.json()
    print("Patched post:")
    print(f"  ID: {patched_post['id']}")
    print(f"  Evaluation Score: {patched_post['evaluation']['score']}")
    print(f"  Strengths count: {len(patched_post['evaluation']['strengths'])}")
    print(f"  Critique count: {len(patched_post['evaluation']['critique'])}")
    print(f"  Suggestions count: {len(patched_post['evaluation']['suggestions'])}")
    
    # 5. Clean up by deleting the post
    print(f"\n5. Deleting test post {post_id}...")
    del_res = session.delete(f"{base_url}/posts/{post_id}")
    if del_res.status_code != 200:
        print(f"Delete failed: {del_res.status_code} - {del_res.text}")
        sys.exit(1)
    print("Delete result:", del_res.json())
    
    print("\nAPI Integration flow completed successfully!")

if __name__ == "__main__":
    main()
