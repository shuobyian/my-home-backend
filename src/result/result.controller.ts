import { Controller, Get, Post, Query } from '@nestjs/common';
import { Tool } from 'src/item/type/Tool';
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
  ) {
    return this.resultService.findAllPage(page, size, name, count, tool);
  }
}
