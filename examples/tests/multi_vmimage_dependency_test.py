mport logging
import os

from avocado import Test
from avocado.core.settings import settings


class MultiVmimageDependencyTest(Test):
    """
    Test to verify multiple vmimage dependencies with the new multi-vmimage type.
    
    This test demonstrates how to use the multi-vmimage dependency type to
    download multiple VM images in a single dependency.
    
    :avocado: dependency={"type": "multi-vmimage", "images": [
        {"provider": "ubuntu", "version": "22.04", "arch": "x86_64"},
        {"provider": "fedora", "version": "41", "arch": "x86_64"}
    ]}
    """
    
    def test_multi_vmimage_dependency(self):
        """
        Verify that multiple VM images were downloaded by the multi-vmimage dependency.
        """
        # Get cache directory from settings
        cache_dir = settings.as_dict().get("datadir.paths.cache_dirs")[0]
        cache_base = os.path.join(cache_dir, "by_location")
        
        # The images should be in the cache since the runner downloaded them
        self.assertTrue(
            os.path.exists(cache_base), f"Cache directory {cache_base} does not exist"
        )
        
        # Log cache contents for debugging
        self.log.info("Cache directory contents:")
        ubuntu_found = False
        fedora_found = False
        
        for root, _, files in os.walk(cache_base):
            for f in files:
                if f.endswith((".qcow2", ".raw", ".img")):
                    filepath = os.path.join(root, f)
                    self.log.info("Found image: %s", filepath)
                    
                    # Check for Ubuntu and Fedora images
                    if "ubuntu-22.04-server-cloudimg-amd64.img" in filepath:
                        ubuntu_found = True
                        self.log.info("Found Ubuntu 22.04 image")
                    
                    if "Fedora-Cloud-Base-Generic-41" in filepath and "x86_64" in filepath:
                        fedora_found = True
                        self.log.info("Found Fedora 41 x86_64 image")
        
        # Verify both images were found
        self.assertTrue(ubuntu_found, "Ubuntu 22.04 image not found in cache")
        self.assertTrue(fedora_found, "Fedora 41 x86_64 image not found in cache")
