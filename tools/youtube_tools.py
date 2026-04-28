from tools.auth import get_google_service


def search_videos(query: str, max_results: int = 5) -> dict:
    service = get_google_service("youtube", "v3")
    result = service.search().list(
        part="snippet",
        type="video",
        q=query,
        maxResults=max_results,
    ).execute()

    videos = []
    for item in result.get("items", []):
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        videos.append({
            "video_id": video_id,
            "title": snippet["title"],
            "channel": snippet["channelTitle"],
            "published_at": snippet["publishedAt"],
            "url": f"https://www.youtube.com/watch?v={video_id}",
        })

    return {"query": query, "results": videos}


def list_my_videos(max_results: int = 10) -> dict:
    service = get_google_service("youtube", "v3")

    channel_resp = service.channels().list(part="snippet,contentDetails", mine=True).execute()
    items = channel_resp.get("items", [])
    if not items:
        return {"channel_title": "", "video_count": 0, "videos": []}

    channel = items[0]
    channel_title = channel["snippet"]["title"]
    uploads_playlist_id = channel["contentDetails"]["relatedPlaylists"]["uploads"]

    playlist_resp = service.playlistItems().list(
        part="snippet",
        playlistId=uploads_playlist_id,
        maxResults=max_results,
    ).execute()

    video_ids = [
        item["snippet"]["resourceId"]["videoId"]
        for item in playlist_resp.get("items", [])
    ]

    if not video_ids:
        return {"channel_title": channel_title, "video_count": 0, "videos": []}

    stats_resp = service.videos().list(
        part="snippet,statistics",
        id=",".join(video_ids),
    ).execute()

    videos = []
    for item in stats_resp.get("items", []):
        stats = item.get("statistics", {})
        snippet = item["snippet"]
        vid_id = item["id"]
        videos.append({
            "video_id": vid_id,
            "title": snippet["title"],
            "published_at": snippet["publishedAt"],
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "url": f"https://www.youtube.com/watch?v={vid_id}",
        })

    return {"channel_title": channel_title, "video_count": len(videos), "videos": videos}
