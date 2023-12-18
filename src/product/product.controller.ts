import { Body, Controller, Get, Post } from '@nestjs/common';
import { ReadProductDto } from 'src/product/dto/read-product-dto';
import { ProductService } from 'src/product/product.service';

@Controller('product')
export class ProductController {
  constructor(private readonly productService: ProductService) {}

  @Post('/login')
  login(@Body() body: { password: string }) {
    return this.productService.login(body);
  }

  @Get()
  findAll() {
    return this.productService.findAll();
  }

  @Post()
  createAll(@Body('products') products: ReadProductDto[]) {
    return this.productService.createAll(products);
  }
}
