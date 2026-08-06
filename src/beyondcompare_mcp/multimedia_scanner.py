"""
Multimedia Drive Scanner Module

Provides specialized tools for scanning and managing multimedia files
across multiple drives with duplicate detection and sync recommendations.
"""

import hashlib
import logging
import os
import platform
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MultimediaDriveScanner:
    """Scanner for multimedia files across multiple drives."""

    # Sandra's drive configuration
    MULTIMEDIA_DRIVES = ["E:", "F:", "K:", "L:"]
    MULTIMEDIA_FOLDER = "multimedia files"

    # Media file type categories
    MEDIA_TYPES = {
        "video": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".m4v", ".webm", ".mpg", ".mpeg"},
        "audio": {".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".wma", ".opus"},
        "images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".raw", ".webp", ".svg"},
        "documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".epub", ".mobi"},
    }

    # Minimum file size to consider for processing (avoid tiny files)
    MIN_FILE_SIZE = 1024  # 1KB

    def __init__(self):
        """Initialize the multimedia scanner."""
        self.scan_results = {}
        self.duplicates_cache = {}

    def detect_available_drives(self) -> list[str]:
        """Detect which of Sandra's multimedia drives are available.

        Returns:
            List of available drive letters
        """
        available_drives = []

        for drive in self.MULTIMEDIA_DRIVES:
            drive_path = Path(drive) / self.MULTIMEDIA_FOLDER
            if drive_path.exists():
                available_drives.append(drive)
                logger.info(f"Found multimedia drive: {drive} -> {drive_path}")
            else:
                logger.warning(f"Multimedia drive not available: {drive} -> {drive_path}")

        return available_drives

    def scan_multimedia_drives(
        self, drives: list[str] | None = None, recent_days: int | None = None, file_types: list[str] | None = None
    ) -> dict[str, Any]:
        """Scan multimedia drives for complete inventory.

        Args:
            drives: Specific drives to scan (default: all available)
            recent_days: Only include files modified in last N days
            file_types: Filter by media types ('video', 'audio', 'images', 'documents')

        Returns:
            Complete inventory with statistics and file details
        """
        logger.info("Starting multimedia drive scan...")
        start_time = time.time()

        # Detect available drives
        if drives is None:
            drives = self.detect_available_drives()

        if not drives:
            return {
                "success": False,
                "error": "No multimedia drives found",
                "drives_checked": self.MULTIMEDIA_DRIVES,
                "multimedia_folder": self.MULTIMEDIA_FOLDER,
            }

        # Calculate cutoff date for recent files
        recent_cutoff = None
        if recent_days:
            recent_cutoff = time.time() - (recent_days * 24 * 60 * 60)

        # Build file type filter
        extensions_filter = set()
        if file_types:
            for file_type in file_types:
                if file_type in self.MEDIA_TYPES:
                    extensions_filter.update(self.MEDIA_TYPES[file_type])
        else:
            # Include all media types
            for media_type in self.MEDIA_TYPES.values():
                extensions_filter.update(media_type)

        # Scan each drive
        scan_results = {}
        total_files = 0
        total_size = 0

        for drive in drives:
            logger.info(f"Scanning drive {drive}...")
            drive_path = Path(drive) / self.MULTIMEDIA_FOLDER

            if not drive_path.exists():
                scan_results[drive] = {
                    "success": False,
                    "error": f"Path not found: {drive_path}",
                    "path": str(drive_path),
                }
                continue

            # Scan drive recursively
            drive_files = []
            drive_size = 0
            drive_stats = defaultdict(lambda: {"count": 0, "size": 0})

            try:
                for root, _dirs, files in os.walk(drive_path):
                    root_path = Path(root)

                    for file in files:
                        file_path = root_path / file

                        # Check file extension
                        file_ext = file_path.suffix.lower()
                        if file_ext not in extensions_filter:
                            continue

                        # Get file stats
                        try:
                            stat_info = file_path.stat()
                            file_size = stat_info.st_size
                            file_mtime = stat_info.st_mtime
                        except OSError as e:
                            logger.warning(f"Could not stat file {file_path}: {e}")
                            continue

                        # Skip tiny files
                        if file_size < self.MIN_FILE_SIZE:
                            continue

                        # Filter by recent files if requested
                        if recent_cutoff and file_mtime < recent_cutoff:
                            continue

                        # Determine media type
                        media_type = self._get_media_type(file_ext)

                        # Build file info
                        file_info = {
                            "name": file_path.name,
                            "path": str(file_path),
                            "relative_path": str(file_path.relative_to(drive_path)),
                            "size": file_size,
                            "size_mb": round(file_size / (1024 * 1024), 2),
                            "modified_time": file_mtime,
                            "extension": file_ext,
                            "media_type": media_type,
                        }

                        drive_files.append(file_info)
                        drive_size += file_size
                        drive_stats[media_type]["count"] += 1
                        drive_stats[media_type]["size"] += file_size

                # Get drive space info
                drive_space = self._get_drive_space(drive)

                scan_results[drive] = {
                    "success": True,
                    "path": str(drive_path),
                    "files": drive_files,
                    "file_count": len(drive_files),
                    "total_size": drive_size,
                    "total_size_gb": round(drive_size / (1024 * 1024 * 1024), 2),
                    "media_stats": dict(drive_stats),
                    "drive_space": drive_space,
                    "scan_filters": {
                        "recent_days": recent_days,
                        "file_types": file_types,
                        "extensions": list(extensions_filter),
                    },
                }

                total_files += len(drive_files)
                total_size += drive_size

            except Exception as e:
                logger.error(f"Error scanning drive {drive}: {e}", exc_info=True)
                scan_results[drive] = {"success": False, "error": str(e), "path": str(drive_path)}

        scan_time = round(time.time() - start_time, 2)

        # Store results for duplicate detection
        self.scan_results = scan_results

        return {
            "success": True,
            "scan_time_seconds": scan_time,
            "drives_scanned": drives,
            "total_files": total_files,
            "total_size_gb": round(total_size / (1024 * 1024 * 1024), 2),
            "results": scan_results,
            "scan_filters": {"recent_days": recent_days, "file_types": file_types},
            "summary": self._generate_scan_summary(scan_results),
        }

    def find_multimedia_duplicates(
        self,
        drives: list[str] | None = None,
        min_size_mb: float = 0.1,
        file_types: list[str] | None = None,
        use_content_hash: bool = True,
    ) -> dict[str, Any]:
        """Find duplicate multimedia files across drives.

        Args:
            drives: Specific drives to check (default: use last scan results)
            min_size_mb: Minimum file size in MB to check for duplicates
            file_types: Filter by media types
            use_content_hash: Use content hash for accurate detection (slower but better)

        Returns:
            Dictionary with duplicate groups and recommendations
        """
        logger.info("Finding multimedia duplicates...")
        start_time = time.time()

        # Use existing scan results or scan now
        if not self.scan_results or drives:
            scan_result = self.scan_multimedia_drives(drives=drives, file_types=file_types)
            if not scan_result["success"]:
                return scan_result

        min_size_bytes = int(min_size_mb * 1024 * 1024)

        # Collect all files across drives
        all_files = []
        for drive, result in self.scan_results.items():
            if not result.get("success", False):
                continue

            for file_info in result.get("files", []):
                if file_info["size"] >= min_size_bytes:
                    file_info["drive"] = drive
                    all_files.append(file_info)

        logger.info(f"Checking {len(all_files)} files for duplicates...")

        # Group by size first (quick filter)
        size_groups = defaultdict(list)
        for file_info in all_files:
            size_groups[file_info["size"]].append(file_info)

        # Find potential duplicates (same size)
        potential_duplicates = {size: files for size, files in size_groups.items() if len(files) > 1}

        duplicate_groups = []
        total_duplicate_size = 0

        for size, files in potential_duplicates.items():
            if use_content_hash:
                # Group by content hash for accurate detection
                hash_groups = defaultdict(list)

                for file_info in files:
                    try:
                        file_hash = self._calculate_file_hash(file_info["path"])
                        hash_groups[file_hash].append(file_info)
                    except Exception as e:
                        logger.warning(f"Could not hash file {file_info['path']}: {e}")
                        continue

                # Process hash groups
                for file_hash, hash_files in hash_groups.items():
                    if len(hash_files) > 1:
                        duplicate_size = (len(hash_files) - 1) * size
                        total_duplicate_size += duplicate_size

                        duplicate_groups.append(
                            {
                                "hash": file_hash,
                                "size": size,
                                "size_mb": round(size / (1024 * 1024), 2),
                                "duplicate_count": len(hash_files),
                                "files": hash_files,
                                "potential_savings_mb": round(duplicate_size / (1024 * 1024), 2),
                                "recommendation": self._generate_duplicate_recommendation(hash_files),
                            }
                        )
            else:
                # Simple name-based grouping (faster but less accurate)
                name_groups = defaultdict(list)
                for file_info in files:
                    name_groups[file_info["name"]].append(file_info)

                for name, name_files in name_groups.items():
                    if len(name_files) > 1:
                        duplicate_size = (len(name_files) - 1) * size
                        total_duplicate_size += duplicate_size

                        duplicate_groups.append(
                            {
                                "name": name,
                                "size": size,
                                "size_mb": round(size / (1024 * 1024), 2),
                                "duplicate_count": len(name_files),
                                "files": name_files,
                                "potential_savings_mb": round(duplicate_size / (1024 * 1024), 2),
                                "recommendation": self._generate_duplicate_recommendation(name_files),
                                "detection_method": "name_and_size",
                            }
                        )

        # Sort by potential savings (largest first)
        duplicate_groups.sort(key=lambda x: x["potential_savings_mb"], reverse=True)

        scan_time = round(time.time() - start_time, 2)

        return {
            "success": True,
            "scan_time_seconds": scan_time,
            "detection_method": "content_hash" if use_content_hash else "name_and_size",
            "total_files_checked": len(all_files),
            "duplicate_groups": duplicate_groups,
            "total_duplicate_groups": len(duplicate_groups),
            "total_duplicate_files": sum(group["duplicate_count"] - 1 for group in duplicate_groups),
            "total_savings_gb": round(total_duplicate_size / (1024 * 1024 * 1024), 2),
            "recommendations": self._generate_cleanup_recommendations(duplicate_groups),
        }

    def get_usb_drives(self) -> list[dict[str, Any]]:
        """Detect connected USB drives.

        Returns:
            List of USB drive information
        """
        usb_drives = []

        # System/NVMe drives to exclude (C:, D:, N: are NVMe/system drives)
        SYSTEM_DRIVES = ["C:", "D:", "N:"]

        if platform.system() == "Windows":
            try:
                import win32api
                import win32file

                drives = win32api.GetLogicalDriveStrings()
                drives = drives.split("\000")[:-1]  # Remove empty string at end

                # Track physical drives to group partitions
                physical_drives = {}  # physical_drive_id -> list of drive letters

                for drive in drives:
                    drive_letter = drive.rstrip("\\")

                    # Skip system/NVMe drives (C:, D:, N:)
                    if drive_letter.upper() in [d.upper() for d in SYSTEM_DRIVES]:
                        continue

                    try:
                        drive_type = win32file.GetDriveType(drive)
                        # Type 2 = Removable drive (USB, floppy, etc.)
                        # Type 3 = Fixed drive (but may be external USB drives that Windows treats as fixed)
                        # Include both removable and fixed drives (E:, F:, K:, L: are on a 15TB USB drive)
                        if drive_type in [2, 3]:
                            space_info = self._get_drive_space(drive_letter)
                            # Only include if it's actually a valid drive with space
                            if space_info.get("total_gb", 0) > 0:
                                # Try to get physical drive number to group partitions
                                physical_drive_id = self._get_physical_drive_id(drive_letter)

                                drive_info = {
                                    "drive_letter": drive_letter,
                                    "label": self._get_drive_label(drive_letter),
                                    "space_info": space_info,
                                    "multimedia_folder_exists": (Path(drive_letter) / self.MULTIMEDIA_FOLDER).exists(),
                                    "drive_type": "removable" if drive_type == 2 else "fixed",
                                    "detection_method": "win32api",
                                }

                                # Group by physical drive if we can detect it
                                if physical_drive_id:
                                    if physical_drive_id not in physical_drives:
                                        physical_drives[physical_drive_id] = []
                                    physical_drives[physical_drive_id].append(drive_info)
                                    drive_info["physical_drive_id"] = physical_drive_id
                                else:
                                    usb_drives.append(drive_info)

                    except Exception as e:
                        logger.warning(f"Could not get info for drive {drive_letter}: {e}")

                # Add grouped drives (if multiple partitions on same physical drive, add as one entry)
                for physical_id, partitions in physical_drives.items():
                    if len(partitions) > 1:
                        # Multiple partitions on same physical drive - create grouped entry
                        total_size = sum(p["space_info"].get("total_gb", 0) for p in partitions)
                        total_free = sum(p["space_info"].get("free_gb", 0) for p in partitions)
                        total_used = sum(p["space_info"].get("used_gb", 0) for p in partitions)

                        # Use the first partition's label or create a combined label
                        primary_label = partitions[0]["label"]
                        if primary_label == "Unlabeled":
                            primary_label = f"USB Drive ({', '.join(p['drive_letter'] for p in partitions)})"

                        usb_drives.append(
                            {
                                "drive_letter": f"{partitions[0]['drive_letter']} (+{len(partitions) - 1} partitions)",
                                "label": primary_label,
                                "space_info": {
                                    "total_gb": round(total_size, 2),
                                    "used_gb": round(total_used, 2),
                                    "free_gb": round(total_free, 2),
                                    "used_percent": round((total_used / total_size * 100) if total_size > 0 else 0, 1),
                                },
                                "multimedia_folder_exists": any(p["multimedia_folder_exists"] for p in partitions),
                                "drive_type": partitions[0]["drive_type"],
                                "detection_method": "win32api",
                                "physical_drive_id": physical_id,
                                "partitions": [p["drive_letter"] for p in partitions],
                                "partition_details": partitions,
                            }
                        )
                    else:
                        # Single partition, add directly
                        usb_drives.append(partitions[0])

            except ImportError:
                logger.warning("win32api not available - using fallback USB detection")
                # Fallback: try common USB drive letters (exclude system drives C:, D:, N:)
                SYSTEM_DRIVES = ["C:", "D:", "N:"]
                for letter in "EFGHIJKLMNOPQRSTUVWXYZ":
                    drive_letter = f"{letter}:"
                    # Skip system/NVMe drives
                    if drive_letter.upper() in [d.upper() for d in SYSTEM_DRIVES]:
                        continue
                    drive_path = Path(drive_letter)
                    try:
                        if drive_path.exists() and drive_path.is_dir():
                            space_info = self._get_drive_space(drive_letter)
                            if space_info.get("total_gb", 0) > 0:  # Valid drive
                                usb_drives.append(
                                    {
                                        "drive_letter": drive_letter,
                                        "label": "Unknown (win32api not available)",
                                        "space_info": space_info,
                                        "multimedia_folder_exists": (
                                            Path(drive_letter) / self.MULTIMEDIA_FOLDER
                                        ).exists(),
                                        "detection_method": "fallback",
                                    }
                                )
                    except Exception:
                        continue

        return usb_drives

    def _get_media_type(self, extension: str) -> str:
        """Determine media type from file extension."""
        extension = extension.lower()

        for media_type, extensions in self.MEDIA_TYPES.items():
            if extension in extensions:
                return media_type

        return "other"

    def _get_drive_space(self, drive: str) -> dict[str, Any]:
        """Get drive space information."""
        try:
            if platform.system() == "Windows":
                import shutil

                total, used, free = shutil.disk_usage(drive)
                return {
                    "total_gb": round(total / (1024 * 1024 * 1024), 2),
                    "used_gb": round(used / (1024 * 1024 * 1024), 2),
                    "free_gb": round(free / (1024 * 1024 * 1024), 2),
                    "used_percent": round((used / total) * 100, 1),
                }
        except Exception as e:
            logger.warning(f"Could not get space info for {drive}: {e}")

        return {"error": "Could not retrieve drive space information"}

    def _get_physical_drive_id(self, drive_letter: str) -> str | None:
        """Get physical drive ID to identify if multiple partitions are on same drive.

        Args:
            drive_letter: Drive letter (e.g., 'E:')

        Returns:
            Physical drive identifier string or None if cannot be determined
        """
        try:
            if platform.system() == "Windows":
                import win32api

                # Get volume GUID path
                try:
                    # Try to get volume information
                    volume_info = win32api.GetVolumeInformation(drive_letter + "\\")
                    volume_serial = volume_info[1]  # Serial number

                    # Use volume serial as physical drive identifier
                    # Drives on same physical device often share characteristics
                    # This is a heuristic - not perfect but better than nothing
                    if volume_serial:
                        return f"vol_{volume_serial}"
                except Exception:
                    pass

                # Alternative: Try to get disk number using WMI (more accurate but requires WMI)
                try:
                    import wmi

                    c = wmi.WMI()
                    for disk in c.Win32_LogicalDisk():
                        if disk.DeviceID == drive_letter:
                            # Get the physical disk this partition belongs to
                            for partition in c.Win32_LogicalDiskToPartition():
                                if partition.Dependent == disk.DeviceID:
                                    for disk_drive in c.Win32_DiskDriveToDiskPartition():
                                        if disk_drive.Dependent == partition.Antecedent:
                                            # Extract disk number from Antecedent
                                            disk_id = disk_drive.Antecedent.split("=")[1].strip('"')
                                            return f"disk_{disk_id}"
                except ImportError:
                    # WMI not available, skip
                    pass
                except Exception:
                    # WMI call failed, skip
                    pass
        except Exception:
            pass
        return None

    def _get_drive_label(self, drive: str) -> str:
        """Get drive volume label."""
        try:
            if platform.system() == "Windows":
                try:
                    import win32api

                    return win32api.GetVolumeInformation(drive + "\\")[0] or "Unlabeled"
                except (ImportError, Exception):
                    # Fallback without win32api or if call fails
                    return "Unknown Label"
        except Exception:
            pass
        return "Unknown"

    def _calculate_file_hash(self, file_path: str, chunk_size: int = 8192) -> str:
        """Calculate SHA-256 hash of file content."""
        hasher = hashlib.sha256()

        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)

        return hasher.hexdigest()

    def _generate_duplicate_recommendation(self, files: list[dict[str, Any]]) -> str:
        """Generate recommendation for handling duplicates."""
        if len(files) <= 1:
            return "No action needed"

        # Sort by drive preference (E: < F: < K: < L:)
        drive_priority = {drive: idx for idx, drive in enumerate(self.MULTIMEDIA_DRIVES)}
        files_sorted = sorted(files, key=lambda f: drive_priority.get(f["drive"], 999))

        keep_file = files_sorted[0]
        remove_files = files_sorted[1:]

        recommendation = f"KEEP: {keep_file['drive']}\\{keep_file['relative_path']}\n"
        recommendation += "REMOVE:\n"

        for file_info in remove_files:
            recommendation += f"  - {file_info['drive']}\\{file_info['relative_path']}\n"

        return recommendation.strip()

    def _generate_cleanup_recommendations(self, duplicate_groups: list[dict[str, Any]]) -> list[str]:
        """Generate overall cleanup recommendations."""
        if not duplicate_groups:
            return ["No duplicates found - your multimedia collection is well organized!"]

        recommendations = []

        # High impact duplicates (>100MB savings)
        high_impact = [g for g in duplicate_groups if g["potential_savings_mb"] > 100]
        if high_impact:
            recommendations.append(
                f"🎯 HIGH IMPACT: {len(high_impact)} duplicate groups could save "
                f"{sum(g['potential_savings_mb'] for g in high_impact):.1f}MB"
            )

        # Most common duplicate types
        media_type_counts = defaultdict(int)
        for group in duplicate_groups:
            for file_info in group["files"]:
                media_type_counts[file_info["media_type"]] += 1

        if media_type_counts:
            top_type = max(media_type_counts, key=media_type_counts.get)
            recommendations.append(
                f"📊 Most duplicated media type: {top_type} ({media_type_counts[top_type]} duplicate files)"
            )

        # Drive distribution
        drive_duplicates = defaultdict(int)
        for group in duplicate_groups:
            for file_info in group["files"]:
                drive_duplicates[file_info["drive"]] += 1

        if drive_duplicates:
            most_duplicate_drive = max(drive_duplicates, key=drive_duplicates.get)
            recommendations.append(
                f"💾 Drive with most duplicates: {most_duplicate_drive} "
                f"({drive_duplicates[most_duplicate_drive]} files)"
            )

        recommendations.append("💡 TIP: Start with largest duplicates first for maximum space savings")

        return recommendations

    def _generate_scan_summary(self, scan_results: dict[str, Any]) -> dict[str, Any]:
        """Generate a summary of scan results."""
        successful_drives = [drive for drive, result in scan_results.items() if result.get("success", False)]

        if not successful_drives:
            return {"error": "No drives scanned successfully"}

        # Aggregate statistics
        total_files = sum(
            result.get("file_count", 0) for result in scan_results.values() if result.get("success", False)
        )

        total_size_gb = sum(
            result.get("total_size_gb", 0) for result in scan_results.values() if result.get("success", False)
        )

        # Media type distribution
        media_distribution = defaultdict(int)
        for result in scan_results.values():
            if not result.get("success", False):
                continue

            for media_type, stats in result.get("media_stats", {}).items():
                media_distribution[media_type] += stats.get("count", 0)

        # Drive space summary
        drive_space_summary = {}
        for drive in successful_drives:
            result = scan_results[drive]
            space_info = result.get("drive_space", {})
            if "used_percent" in space_info:
                drive_space_summary[drive] = {
                    "used_percent": space_info["used_percent"],
                    "free_gb": space_info.get("free_gb", 0),
                    "multimedia_size_gb": result.get("total_size_gb", 0),
                }

        return {
            "successful_drives": successful_drives,
            "total_files": total_files,
            "total_size_gb": round(total_size_gb, 2),
            "media_distribution": dict(media_distribution),
            "drive_space_summary": drive_space_summary,
            "largest_collection": max(
                (
                    (drive, result.get("file_count", 0))
                    for drive, result in scan_results.items()
                    if result.get("success", False)
                ),
                key=lambda x: x[1],
                default=("none", 0),
            )[0],
        }
