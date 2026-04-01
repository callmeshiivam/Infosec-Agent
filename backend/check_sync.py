import os
from pathlib import Path
from services import rag_engine

# 1. Get files on disk
uploads_dir = Path("data/uploads")
disk_files = {f.name for f in uploads_dir.iterdir() if f.is_file()}
print(f"Files on disk: {len(disk_files)}")

# 2. Get files in ChromaDB
collection = rag_engine._get_vectorstore()._collection
results = collection.get(include=["metadatas"])
chroma_files = {m["filename"] for m in results["metadatas"]} if results["metadatas"] else set()
print(f"Files in ChromaDB: {len(chroma_files)}")

# 3. Find discrepancies
missing_from_chroma = disk_files - chroma_files
missing_from_disk = chroma_files - disk_files

print(f"\nMissing from Chroma (on disk but no chunks): {len(missing_from_chroma)}")
for f in sorted(list(missing_from_chroma))[:10]:
    print(f"  - {f}")

print(f"\nMissing from Disk (in Chroma but file deleted): {len(missing_from_disk)}")
for f in sorted(list(missing_from_disk))[:10]:
    print(f"  - {f}")
