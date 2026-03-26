"""Tests for color depth conversion utilities."""

from kida.utils.color_convert import index256_to_basic_fg, rgb_to_256, rgb_to_basic_fg


class TestRgbTo256:
    def test_pure_red(self):
        assert rgb_to_256(255, 0, 0) == 196

    def test_pure_green(self):
        assert rgb_to_256(0, 255, 0) == 46

    def test_pure_blue(self):
        assert rgb_to_256(0, 0, 255) == 21

    def test_black(self):
        result = rgb_to_256(0, 0, 0)
        assert result in (0, 16, 232)  # cube black or grayscale

    def test_white(self):
        result = rgb_to_256(255, 255, 255)
        assert result in (15, 231, 255)  # cube white or grayscale

    def test_gray_prefers_grayscale_ramp(self):
        result = rgb_to_256(128, 128, 128)
        assert 232 <= result <= 255  # should pick grayscale ramp

    def test_returns_int(self):
        assert isinstance(rgb_to_256(100, 150, 200), int)

    def test_range_valid(self):
        for r in (0, 128, 255):
            for g in (0, 128, 255):
                for b in (0, 128, 255):
                    idx = rgb_to_256(r, g, b)
                    assert 0 <= idx <= 255


class TestRgbToBasicFg:
    def test_pure_red_maps_to_red(self):
        assert rgb_to_basic_fg(255, 0, 0) in (31, 91)  # red or bright red

    def test_pure_green_maps_to_green(self):
        assert rgb_to_basic_fg(0, 255, 0) in (32, 92)

    def test_pure_blue_maps_to_blue(self):
        assert rgb_to_basic_fg(0, 0, 255) in (34, 94)

    def test_white_maps_to_white(self):
        assert rgb_to_basic_fg(255, 255, 255) in (37, 97)

    def test_black_maps_to_black(self):
        assert rgb_to_basic_fg(0, 0, 0) == 30

    def test_returns_valid_sgr(self):
        valid = set(range(30, 38)) | set(range(90, 98))
        for r in (0, 128, 255):
            for g in (0, 128, 255):
                for b in (0, 128, 255):
                    assert rgb_to_basic_fg(r, g, b) in valid


class TestIndex256ToBasicFg:
    def test_basic_passthrough(self):
        # Index 0-15 should map directly
        assert index256_to_basic_fg(0) == 30  # black
        assert index256_to_basic_fg(1) == 31  # red
        assert index256_to_basic_fg(9) == 91  # bright red

    def test_cube_index(self):
        valid = set(range(30, 38)) | set(range(90, 98))
        assert index256_to_basic_fg(196) in valid  # red from cube

    def test_grayscale_index(self):
        valid = set(range(30, 38)) | set(range(90, 98))
        assert index256_to_basic_fg(240) in valid  # mid gray

    def test_all_indices_valid(self):
        valid = set(range(30, 38)) | set(range(90, 98))
        for i in range(256):
            assert index256_to_basic_fg(i) in valid
