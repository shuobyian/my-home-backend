import { Body, Controller, Get, Post, Query } from '@nestjs/common';
import { Market } from 'src/market/entities/market.entity';
import { Category } from 'src/product/type/Category';
import { Tool } from 'src/product/type/Tool';
import { ResultService } from 'src/result/result.service';

@Controller('result')
export class ResultController {
  constructor(private readonly resultService: ResultService) {}

  @Post()
  createAll() {
    return this.resultService.createAll();
  }

  @Get()
  findAll(
    @Query('page') page: number,
    @Query('size') size: number,
    @Query('name') name?: string,
    @Query('count') count?: number,
    @Query('tool') tool?: Tool,
    @Query('category') category?: Category,
  ) {
    return this.resultService.findAllPage(
      page,
      size,
      name,
      count,
      tool,
      category,
    );
  }

  @Post('calculator')
  calculator(@Body('markets') markets: Market[]) {
    return this.resultService.calculator(markets);
  }
}
