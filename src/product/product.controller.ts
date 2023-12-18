import {
  Body,
  Controller,
  Delete,
  Get,
  Post,
  Put,
  Query,
} from '@nestjs/common';
import { ReadProductDto } from 'src/product/dto/read-product-dto';
import { UpdateProductDto } from 'src/product/dto/update-product-dto';
import { ProductService } from 'src/product/product.service';

@Controller('product')
export class ProductController {
  constructor(private readonly productService: ProductService) {}

  @Post('/login')
  login(@Body() body: { password: string }) {
    return this.productService.login(body);
  }

  @Get()
  findAll(@Query('page') page: number, @Query('size') size: number) {
    return this.productService.findAllPage(page, size);
  }

  @Post('all')
  createAll(@Body('products') products: ReadProductDto[]) {
    return this.productService.createAll(products);
  }

  @Post()
  create(@Body() product: ReadProductDto) {
    return this.productService.create(product);
  }

  @Put()
  update(@Body() product: UpdateProductDto) {
    return this.productService.update(product);
  }

  @Delete()
  delete(@Body() ids: number[]) {
    return this.productService.delete(ids);
  }
}
