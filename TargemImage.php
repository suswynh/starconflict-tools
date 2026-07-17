<?php

namespace Games\StarConflict;

use DataStream;
use ErrorHandler;
use FileRaw;

class TargemImage {

	public static function convert( $file, $dstFile ) {

		// заголовочный файл
		$headerFile = $file . ".tfh";

		$header = GameFS::loadFile( $headerFile );

		if( !$header ) {
			return ErrorHandler::error( "Не удалось прочитать файл заголовка '$headerFile'" );
		}

		// заголовок
		$stream = new DataStream();
		$stream->set( $header );

		$imageSize = $stream->uint32();
		$imageWidth = ($imageSize & 0xFFFFFF) / 16;
		$imageHeight = ($imageSize >> 24) << 6;

		$mips = $stream->uint8();
		$mipsCount = $mips & 0x0F;
		$mipsInFile = ($mips & 0xF0) >> 4;

		$format = $stream->uint8();
		$type = $stream->uint8();
		$unknown2 = $stream->uint8();

		// таблица изображений
		$imageTable = array();

		for( $i = 0; $i < $mipsCount; $i++ ) {

			$imageTable[$i] = array(
				'offset' => $stream->uint32(),
				'size'	 => $stream->uint32(),
				'width'	 => $stream->uint32()
			);
		}

		// самое большое изображение
		$image = end( $imageTable );

		switch( $format & 0x0F ) {

			// RGBA
			case 0x0 :
			case 0x5 :
			case 0x6 :
				$imageWidth = $image['width'] / 4;
				$imageHeight = $image['size'] / $image['width'];
				$ddsHeader = self::getDdsHeader( "RGBA", $imageWidth, $imageHeight );
				break;

			// DXT1
			case 0x7 :
			case 0xB :
				$imageWidth = $image['width'] / 2;
				$imageHeight = 4 * $image['size'] / $image['width'];
				$ddsHeader = self::getDdsHeader( "DXT1", $imageWidth, $imageHeight );
				break;

			// DXT3
			case 0x9 :
			case 0xD :
				$imageWidth = $image['width'] / 4;
				$imageHeight = 4 * $image['size'] / $image['width'];
				$ddsHeader = self::getDdsHeader( "DXT3", $imageWidth, $imageHeight );
				break;

			// DXT5
			case 0xA :
			case 0xE :
				$imageWidth = $image['width'] / 4;
				$imageHeight = 4 * $image['size'] / $image['width'];
				$ddsHeader = self::getDdsHeader( "DXT5", $imageWidth, $imageHeight );
				break;

			default :
				$formatString = "0x" . strtoupper( dechex( $format ) );
				ErrorHandler::fatal( "Неизвестный формат {$formatString} текстуры  '$file'" );
		}

		// выбираем источник данных, tfh или tfd
		if( $mipsCount !== $mipsInFile ) {

			$dataFile = $file . ".tfd";
			$data = GameFS::loadFile( $dataFile );

			if( !$data ) {
				return self::error( "Не удалось прочитать файл данных '$dataFile'" );
			}

			$stream->set( $data );
		}

		$stream->seek( $image['offset'] );
		$data = $stream->string( $image['size'] );

		file_put_contents( $dstFile, $ddsHeader . $data );

		return true;

	}

	private static function getDdsHeader( $format, $width, $height ) {

		$ddsHeader = array(
			'dwSize'			  => 124,
			'dwFlags'			  => 0,
			'dwHeight'			  => $height,
			'dwWidth'			  => $width,
			'dwPitchOrLinearSize' => 0,
			'dwDepth'			  => 0,
			'dwMipMapCount'		  => 0,
			'dwReserved1'		  => pack( "V11", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ),
			'ddspf'				  => self::getDdsPixelFormat( $format ),
			'dwCaps'			  => 0x1000,
			'dwCaps2'			  => 0,
			'dwCaps3'			  => 0,
			'dwCaps4'			  => 0,
			'dwReserved2'		  => 0
		);

		switch( $format ) {

			case 'RGBA' :
				$ddsHeader['dwFlags'] = 0x1 | 0x2 | 0x4 | 0x8 | 0x1000;
				$ddsHeader['dwPitchOrLinearSize'] = intdiv( $ddsHeader['dwWidth'] * 32 + 7, 8 );
				break;

			case 'DXT1' :
				$ddsHeader['dwFlags'] = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000;
				$ddsHeader['dwPitchOrLinearSize'] = max( 1, intdiv( $ddsHeader['dwWidth'] + 3, 4 ) ) * 8;
				break;

			case 'DXT3' :
			case 'DXT5' :
				$ddsHeader['dwFlags'] = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000;
				$ddsHeader['dwPitchOrLinearSize'] = max( 1, intdiv( $ddsHeader['dwWidth'] + 3, 4 ) ) * 16;
				break;
		}

		return pack( "a4V7a44a32V5",
			"DDS ",
			$ddsHeader['dwSize'],
			$ddsHeader['dwFlags'],
			$ddsHeader['dwHeight'],
			$ddsHeader['dwWidth'],
			$ddsHeader['dwPitchOrLinearSize'],
			$ddsHeader['dwDepth'],
			$ddsHeader['dwMipMapCount'],
			$ddsHeader['dwReserved1'],
			$ddsHeader['ddspf'],
			$ddsHeader['dwCaps'],
			$ddsHeader['dwCaps2'],
			$ddsHeader['dwCaps3'],
			$ddsHeader['dwCaps4'],
			$ddsHeader['dwReserved2']
		);

	}

	private static function getDdsPixelFormat( $format ) {

		$ddsPixelFormat = array(
			'dwSize'		=> 32,
			'dwFlags'		=> 0,
			'dwFourCC'		=> "\x00\x00\x00\x00",
			'dwRGBBitCount' => 0,
			'dwRBitMask'	=> 0,
			'dwGBitMask'	=> 0,
			'dwBBitMask'	=> 0,
			'dwABitMask'	=> 0
		);

		switch( $format ) {

			case 'RGBA' :
				$ddsPixelFormat['dwFlags'] = 0x1 | 0x40;
				$ddsPixelFormat['dwRGBBitCount'] = 32;
				$ddsPixelFormat['dwRBitMask'] = 0x00FF0000;
				$ddsPixelFormat['dwGBitMask'] = 0x0000FF00;
				$ddsPixelFormat['dwBBitMask'] = 0x000000FF;
				$ddsPixelFormat['dwABitMask'] = 0xFF000000;
				break;

			case 'DXT1' :
			case 'DXT3' :
			case 'DXT5' :
				$ddsPixelFormat['dwFlags'] = 0x4;
				$ddsPixelFormat['dwFourCC'] = $format;
				break;
		}

		return pack( "V2a4V5",
			$ddsPixelFormat['dwSize'],
			$ddsPixelFormat['dwFlags'],
			$ddsPixelFormat['dwFourCC'],
			$ddsPixelFormat['dwRGBBitCount'],
			$ddsPixelFormat['dwRBitMask'],
			$ddsPixelFormat['dwGBitMask'],
			$ddsPixelFormat['dwBBitMask'],
			$ddsPixelFormat['dwABitMask']
		);

	}

}
