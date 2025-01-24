mport logging
import os

from avocado import Test
from avocado.core.settings import settings
from avocado.utils import vmimage


class MultiVmimageTest(Test):
    """
    Test to verify multiple vmimage dependencies with proper logging.
    
    This test demonstrates how to set up logging to see the vmimage validation process
    for multiple images.
    
    :avocado: dependency={"type": "vmimage", "provider": "ubuntu", "version": "22.04", "arch": "x86_64"}
    :avocado: dependency={"type": "vmimage", "provider": "fedora", "version": "41", "arch": "x86_64"}
    """
    
    def setUp(self):
        """
        Set up logging for vmimage and asset modules.
        """
        # Set up logging for vmimage module
        vmimage_logger = logging.getLogger('avocado.utils.vmimage')
        vmimage_logger.setLevel(logging.DEBUG)
        
        # Add handler to log to the test's log
        for handler in self.log.handlers:
            vmimage_logger.addHandler(handler)
        
        # Set up logging for asset module
        asset_logger = logging.getLogger('avocado.utils.asset')
        asset_logger.setLevel(logging.DEBUG)
        
        # Add handler to log to the test's log
        for handler in self.log.handlers:
            asset_logger.addHandler(handler)
            
        self.log.info("Logging set up for vmimage and asset modules")

    def test_multi_vmimage(self):
        """
        Verify that multiple VM image dependencies work with proper logging.
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
        
        # Manually trigger vmimage download to see logging
        self.log.info("Manually triggering Ubuntu vmimage download to see logging:")
        try:
            # This should use the cache if the image is already downloaded
            ubuntu_image = vmimage.Image.from_parameters(
                name="ubuntu", 
                version="22.04", 
                arch="x86_64",
                cache_dir=cache_dir
            )
            self.log.info("Ubuntu image path: %s", ubuntu_image.path)
            self.assertTrue(os.path.exists(ubuntu_image.path), f"Ubuntu image file {ubuntu_image.path} does not exist")
        except Exception as e:
            self.fail(f"Failed to get Ubuntu vmimage: {str(e)}")
            
        self.log.info("Manually triggering Fedora vmimage download to see logging:")
        try:
            # This should use the cache if the image is already downloaded
            fedora_image = vmimage.Image.from_parameters(
                name="fedora", 
                version="41", 
                arch="x86_64",
                cache_dir=cache_dir
            )
            self.log.info("Fedora image path: %s", fedora_image.path)
            self.assertTrue(os.path.exists(fedora_image.path), f"Fedora image file {fedora_image.path} does not exist")
        except Exception as e:
            self.fail(f"Failed to get Fedora vmimage: {str(e)}")
