import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from backup_supabase_storage import safe_object_path, verify_archive
from restore_supabase_storage import compare_database_inventory


class StorageRecoveryTests(unittest.TestCase):
    def test_safe_object_path_preserves_nested_paths(self):
        self.assertEqual(
            safe_object_path("private-bucket", "folder/asset.glb"),
            "objects/private-bucket/folder/asset.glb",
        )

    def test_safe_object_path_rejects_traversal(self):
        with self.assertRaises(SystemExit):
            safe_object_path("private-bucket", "../secret.txt")

    def test_archive_verification_checks_object_hashes(self):
        payload = b"allpha-storage-backup"
        item = {
            "bucket_id": "spatial-assets",
            "name": "theme/model.glb",
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "content_type": "model/gltf-binary",
            "created_at": "2026-11-26T00:00:00Z",
            "updated_at": "2026-11-26T00:00:00Z",
        }
        manifest = {
            "project_ref": "dvdziauyvuhcnqhrrrww",
            "captured_at_utc": "2026-11-26T00:00:00Z",
            "bucket_count": 1,
            "object_count": 1,
            "total_bytes": len(payload),
            "buckets": [{"id": "spatial-assets", "name": "spatial-assets", "public": False}],
            "objects": [item],
        }
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "storage.tar"
            with tarfile.open(archive_path, "w:") as archive:
                info = tarfile.TarInfo("objects/spatial-assets/theme/model.glb")
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
                encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
                manifest_info = tarfile.TarInfo("manifest.json")
                manifest_info.size = len(encoded)
                archive.addfile(manifest_info, io.BytesIO(encoded))
            verify_archive(archive_path, manifest)

    def test_restored_database_inventory_must_match_backup(self):
        manifest = {
            "objects": [{
                "bucket_id": "spatial-assets",
                "name": "theme/model.glb",
                "size_bytes": 12,
                "content_type": "model/gltf-binary",
            }]
        }
        inventory = [{
            "bucket_id": "spatial-assets",
            "name": "theme/model.glb",
            "size_bytes": "12",
            "content_type": "model/gltf-binary",
        }]
        compare_database_inventory(manifest, inventory)

    def test_restored_database_inventory_rejects_missing_objects(self):
        manifest = {
            "objects": [{
                "bucket_id": "spatial-assets",
                "name": "theme/model.glb",
                "size_bytes": 12,
                "content_type": "model/gltf-binary",
            }]
        }
        with self.assertRaises(SystemExit):
            compare_database_inventory(manifest, [])


if __name__ == "__main__":
    unittest.main()
